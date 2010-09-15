# This is not supposed to be a useful Python script
while lines:

    # Regular expression that picks up the main section dividers
    div = re.compile(r'^' + conf['section_div'] + \
                     '{' + str(conf['min_length_div']) + r',}$')

    # Cross references are ".. _label:"  - these must be maintained in the
    # same RST file to which the reference refers
    cf = re.compile(r'^\s*\.\. _(.*?):\n')

    # Reload the list of files (don't believe the version that may have been
    # loaded from the pickled environment)
    app.env.find_files(app.config)
    all_files = app.env.found_docs
    for fname in list(all_files):
        name = os.path.join(app.env.srcdir, fname + app.config.source_suffix)

        # We will not comment within these files
        if fname == app.config.master_doc or \
                                 fname.endswith(conf['toc_doc']):
            continue

        subdir, rootname = os.path.split(name)
        basename = rootname.split(app.config.source_suffix)[0]
        f = open(name, 'r')
        try:
            lines = f.readlines()
        finally:
            f.close()

        # This dict has keys="line offset in the RST file for each section",
        # while the corresponding value="file name to which that subsection
        # will be written".
        to_process = {}

