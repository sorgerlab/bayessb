from texttable import Texttable
import TableFactory as tf
from inspect import ismodule
from bayessb.multichain import MCMCSet
import pickle
import inspect

reporter_dict = {}

class Report(object):
    """.. todo:: document this class """

    def __init__(self, chain_filenames, reporters, names=None):
        """Create the Report object and run all reporter functions.

        Parameters
        ----------
        chain_filenames : dict of lists of MCMC filenames.
            The keys in the dict are the names of the groups of chains.  These
            should ideally be descriptive abbreviations, indicating the type of
            model, number of steps run in each chain, etc.  The entries in the
            dict are lists of filenames of pickled MCMC objects,
            representing completed MCMC estimation runs for the given
            model/data.
        reporters : mixed list of reporter functions and/or modules
            The reporter functions should take an instance of
            bayessb.MCMCSet.multichain as an argument and return an
            instance of pysb.report.Result. For inclusion in the report results
            table. If a module is included in the list, any reporter functions
            included in the module (i.e., functions decorated with
            @pysb.report.reporter) will be identified and applied to the
            chains.
        names : optional, list of strings
            Names to be used as the column headers in the report results
            table. If not provided, the keys from the chains dict are used
            as the column names.
        """

        self.chain_filenames = chain_filenames

        # Unpack reporter modules, adding any reporter functions found
        self.reporters = []
        for reporter in reporters:
            if ismodule(reporter):
                self.reporters += reporter_dict[reporter.__name__]
            else:
                self.reporters.append(reporter)

        # Initialize names
        if names is None:
            self.names = chain_filenames.keys()
            #self.names = [c.options.model.name for c in chains]
        else:
            self.names = names

        # Add an empty column to make room for the reporter names
        self.header_names = [''] + self.names

        # Run the reports
        reporter_names = [r.reporter_name for r in self.reporters]
        self.results = [reporter_names]
        for chain_list_name, chain_list in self.chain_filenames.iteritems():
            self.get_results_for_chain_set(chain_list_name, chain_list)

        # Transpose the results list 
        self.results = zip(*self.results)

    def get_results_for_chain_set(self, chain_list_name, chain_list):
        """Takes a list of filenames for a group of chains, initializes
        an MCMCSet object, and calls all of the reporters on the MCMCSet.
        Deferred the loading of MCMCSet objects to this function because
        it means that only one set of chains needs to be included in memory
        at any one time.
        """
        print "Loading chains for %s..." % chain_list_name
        mcmc_set = MCMCSet(chain_list_name)

        # Load the chain files
        mcmc_list = []
        for filename in chain_list:
            mcmc_list.append(pickle.load(open(filename)))

        # Prune and pool the chains in the list
        mcmc_set.initialize_and_pool(mcmc_list, mcmc_list[0].options.nsteps / 2)

        print "Running reporters for %s..." % chain_list_name
        result = []
        for reporter in self.reporters:
            result.append(reporter(mcmc_set))
        self.results.append(result)

    def get_text_table(self, max_width=80):
        """Return the report results as a pretty-printed text table."""
        tt = Texttable(max_width=max_width)
        tt.header(self.header_names)

        text_results = [[r.value if hasattr(r, 'value') else r for r in r_list]
                         for r_list in self.results]

        tt.add_rows(text_results, header=False)
        return tt.draw()

    def write_pdf_table(self, filename):
        """Writes the results table to a PDF file.

        Parameters
        ----------
        filename : string
            The name of the output filename.
        """

        lines = []
        for row in self.results:
            lines.append(tf.TableRow(*map(tf.Cell, row)))

        rowmaker = tf.RowSpec(*map(tf.ColumnSpec, self.header_names))
        table = tf.PDFTable('Results', headers=rowmaker)
        f = open(filename, 'wb')
        f.write(table.render(lines))

    def write_html_table(self, filename):
        """Writes the results table to a HTML file.

        Parameters
        ----------
        filename : string
            The name of the output filename.
        """

        lines = []
        for row in self.results:
            html_row = []
            for result in row:
                # Here we assume it's a pysb.report.Result object
                if hasattr(result, 'link'):
                    if result.link is None:
                        html_row.append(result.value)
                    else:
                        html_row.append('<a href=\'%s\'>%s</a>' %
                                        (result.link, result.value))
                # Handle the case of the row header
                else: 
                    html_row.append(result)

            lines.append(tf.TableRow(*map(tf.Cell, html_row)))

        rowmaker = tf.RowSpec(*map(tf.ColumnSpec, self.header_names))
        table = tf.HTMLTable('Results', headers=rowmaker)
        f = open(filename, 'wb')
        f.write(table.render(lines))

    def write_html_table_with_links(self, filename):
        """A manual re-write of HTML table export to allow inclusion of
        hyperlinks (the TableFactory version escapes the markup)
        """
        # Add some formatting for the overall page
        lines = '<html><head>' \
                '<style type="text/css"><!-- ' \
                'BODY { font-family: sans-serif; } --></style><body>'

        lines += "<table border=1>"

        # Add the headers
        header_string = "<tr><td>"
        header_string += '</td><td>'.join([h for h in self.header_names])
        header_string += "</td></tr>"
        lines += header_string

        for row in self.results:
            html_row = []
            html_row_string = "<tr><td>"
            for result in row:
                # Here we assume it's a pysb.report.Result object
                if hasattr(result, 'link'):
                    # Format the result
                    if isinstance(result.value, float):
                        result_str = '%-.2f' % result.value
                    elif isinstance(result.value, bool):
                        if result.value:
                            result_str = 'True'
                        else:
                            result_str = 'False'
                    else:
                        result_str = str(result.value)

                    if result.link is None:
                        html_row.append(result_str)
                    else:
                        html_row.append("<a href='%s'>%s</a>" %
                                        (result.link, result_str))
                # Handle the case of the row header
                else:
                    html_row.append(str(result))

            html_row_string += '</td><td>'.join(html_row)
            html_row_string += '</td></tr>'
            lines += html_row_string
        lines += "</table>"

        # Add closing tags
        lines += "</body></html>"

        f = open(filename, 'wb')
        f.write(lines)

class Result(object):
    """Stores the results associated with the execution of a reporter function.
    """
    def __init__(self, value, link):
        """Create the Result object.

        Parameters
        ----------
        value : anything
            The return value of a reporter function.
        link : string
            String representing a hyperlink, e.g. to information or
            visualizations supporting the reporter result.
        """
        self.value = value
        self.link = link

# DECORATOR
def reporter(name):
    """Decorator for reporter functions.

    Sets the ``name`` field of the function to indicate its name. The name of
    the reporter function is meant to be a human-readable name for use in
    results summaries.

    The decorator also adds the reporter function to the package-level variable
    ``reporter_dict``, which keeps track of all reporter functions imported (and
    decorated) thus far. The ``reporter_dict`` is indexed by the name of the
    module containing the reporter function, and each key maps to a list of 
    reporter functions.

    Parameters
    ----------
    name : string
        The human-readable name for the reporter function.

    Returns
    -------
    The decorated reporter function.
    """

    if callable(name):
        raise TypeError("The reporter decorator requires a name argument.")
    def wrap(f):
        # Keep track of all reporters in the package level reporter_dict
        reporter_mod_name = inspect.getmodule(f).__name__
        reporter_list = reporter_dict.setdefault(reporter_mod_name, [])
        reporter_list.append(f)
        f.reporter_name = name
        return f
    return wrap