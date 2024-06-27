#!/usr/bin/env python3

# Copyright (c) 2018,2020 Intel Corporation
# Copyright (c) 2022 Nordic Semiconductor ASA
# SPDX-License-Identifier: Apache-2.0

import argparse
from email.utils import parseaddr
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import shlex

from junitparser import TestCase, TestSuite, JUnitXml, Skipped, Error, Failure
import magic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = None

def git(*args, cwd=None, ignore_non_zero=False):
    # Helper for running a Git command. Returns the rstrip()ed stdout output.
    # Called like git("diff"). Exits with SystemError (raised by sys.exit()) on
    # errors if 'ignore_non_zero' is set to False (default: False). 'cwd' is the
    # working directory to use (default: current directory).

    git_cmd = ("git",) + args
    try:
        cp = subprocess.run(git_cmd, capture_output=True, cwd=cwd)
    except OSError as e:
        err(f"failed to run '{cmd2str(git_cmd)}': {e}")

    if not ignore_non_zero and (cp.returncode or cp.stderr):
        err(f"'{cmd2str(git_cmd)}' exited with status {cp.returncode} and/or "
            f"wrote to stderr.\n"
            f"==stdout==\n"
            f"{cp.stdout.decode('utf-8')}\n"
            f"==stderr==\n"
            f"{cp.stderr.decode('utf-8')}\n")

    return cp.stdout.decode("utf-8").rstrip()

def get_shas(refspec):
    """
    Returns the list of Git SHAs for 'refspec'.

    :param refspec:
    :return:
    """
    return git('rev-list',
               f'--max-count={-1 if "." in refspec else 1}', refspec).split()

def get_files(filter=None, paths=None):
    filter_arg = (f'--diff-filter={filter}',) if filter else ()
    paths_arg = ('--', *paths) if paths else ()
    out = git('diff', '--name-only', *filter_arg, COMMIT_RANGE, *paths_arg)
    files = out.splitlines()
    for file in list(files):
        if not os.path.isfile(os.path.join(GIT_TOP, file)):
            # Drop submodule directories from the list.
            files.remove(file)
    return files

class FmtdFailure(Failure):

    def __init__(self, severity, title, file, line=None, col=None, desc=""):
        self.severity = severity
        self.title = title
        self.file = file
        self.line = line
        self.col = col
        self.desc = desc
        description = f':{desc}' if desc else ''
        msg_body = desc or title

        txt = f'\n{title}{description}\nFile:{file}' + \
              (f'\nLine:{line}' if line else '') + \
              (f'\nColumn:{col}' if col else '')
        msg = f'{file}' + (f':{line}' if line else '') + f' {msg_body}'
        typ = severity.lower()

        super().__init__(msg, typ)

        self.text = txt


class ComplianceTest:
    """
    Base class for tests. Inheriting classes should have a run() method and set
    these class variables:

    name:
      Test name

    doc:
      Link to documentation related to what's being tested

    path_hint:
      The path the test runs itself in. This is just informative and used in
      the message that gets printed when running the test.

      There are two magic strings that can be used instead of a path:
      - The magic string "<zephyr-base>" can be used to refer to the
      environment variable ZEPHYR_BASE or, when missing, the calculated base of
      the zephyr tree
      - The magic string "<git-top>" refers to the top-level repository
      directory. This avoids running 'git' to find the top-level directory
      before main() runs (class variable assignments run when the 'class ...'
      statement runs). That avoids swallowing errors, because main() reports
      them to GitHub
    """
    def __init__(self):
        self.case = TestCase(type(self).name, "Guidelines")
        # This is necessary because Failure can be subclassed, but since it is
        # always restored form the element tree, the subclass is lost upon
        # restoring
        self.fmtd_failures = []

    def _result(self, res, text):
        res.text = text.rstrip()
        self.case.result += [res]

    def error(self, text, msg=None, type_="error"):
        """
        Signals a problem with running the test, with message 'msg'.

        Raises an exception internally, so you do not need to put a 'return'
        after error().
        """
        err = Error(msg or f'{type(self).name} error', type_)
        self._result(err, text)

        raise EndTest

    def skip(self, text, msg=None, type_="skip"):
        """
        Signals that the test should be skipped, with message 'msg'.

        Raises an exception internally, so you do not need to put a 'return'
        after skip().
        """
        skpd = Skipped(msg or f'{type(self).name} skipped', type_)
        self._result(skpd, text)

        raise EndTest

    def failure(self, text, msg=None, type_="failure"):
        """
        Signals that the test failed, with message 'msg'. Can be called many
        times within the same test to report multiple failures.
        """
        fail = Failure(msg or f'{type(self).name} issues', type_)
        self._result(fail, text)

    def fmtd_failure(self, severity, title, file, line=None, col=None, desc=""):
        """
        Signals that the test failed, and store the information in a formatted
        standardized manner. Can be called many times within the same test to
        report multiple failures.
        """
        fail = FmtdFailure(severity, title, file, line, col, desc)
        self._result(fail, fail.text)
        self.fmtd_failures.append(fail)

class EndTest(Exception):
    """
    Raised by ComplianceTest.error()/skip() to end the test.

    Tests can raise EndTest themselves to immediately end the test, e.g. from
    within a nested function call.
    """


class Nits(ComplianceTest):
    """
    Checks various nits in added/modified files. Doesn't check stuff that's
    already covered by e.g. checkpatch.pl and pylint.
    """
    name = "Nits"
    doc = "See https://docs.zephyrproject.org/latest/contribute/guidelines.html#coding-style for more details."
    path_hint = "<git-top>"

    def run(self):
        # Loop through added/modified files
        for fname in get_files(filter="d"):
            if "Kconfig" in fname:
                self.check_kconfig_header(fname)
                self.check_redundant_zephyr_source(fname)

            if fname.startswith("dts/bindings/"):
                self.check_redundant_document_separator(fname)

            if fname.endswith((".c", ".conf", ".cpp", ".dts", ".overlay",
                               ".h", ".ld", ".py", ".rst", ".txt", ".yaml",
                               ".yml")) or \
               "Kconfig" in fname or \
               "defconfig" in fname or \
               fname == "README":

                self.check_source_file(fname)

    def check_kconfig_header(self, fname):
        # Checks for a spammy copy-pasted header format

        with open(os.path.join(GIT_TOP, fname), encoding="utf-8") as f:
            contents = f.read()

        # 'Kconfig - yada yada' has a copy-pasted redundant filename at the
        # top. This probably means all of the header was copy-pasted.
        if re.match(r"\s*#\s*(K|k)config[\w.-]*\s*-", contents):
            self.failure(f"""
Please use this format for the header in '{fname}' (see
https://docs.zephyrproject.org/latest/build/kconfig/tips.html#header-comments-and-other-nits):

    # <Overview of symbols defined in the file, preferably in plain English>
    (Blank line)
    # Copyright (c) 2019 ...
    # SPDX-License-Identifier: <License>
    (Blank line)
    (Kconfig definitions)

Skip the "Kconfig - " part of the first line, since it's clear that the comment
is about Kconfig from context. The "# Kconfig - " is what triggers this
failure.
""")

    def check_redundant_zephyr_source(self, fname):
        # Checks for 'source "$(ZEPHYR_BASE)/Kconfig[.zephyr]"', which can be
        # be simplified to 'source "Kconfig[.zephyr]"'

        with open(os.path.join(GIT_TOP, fname), encoding="utf-8") as f:
            # Look for e.g. rsource as well, for completeness
            match = re.search(
                r'^\s*(?:o|r|or)?source\s*"\$\(?ZEPHYR_BASE\)?/(Kconfig(?:\.zephyr)?)"',
                f.read(), re.MULTILINE)

            if match:
                self.failure("""
Redundant 'source "$(ZEPHYR_BASE)/{0}" in '{1}'. Just do 'source "{0}"'
instead. The $srctree environment variable already points to the Zephyr root,
and all 'source's are relative to it.""".format(match.group(1), fname))

    def check_redundant_document_separator(self, fname):
        # Looks for redundant '...' document separators in bindings

        with open(os.path.join(GIT_TOP, fname), encoding="utf-8") as f:
            if re.search(r"^\.\.\.", f.read(), re.MULTILINE):
                self.failure(f"""\
Redundant '...' document separator in {fname}. Binding YAML files are never
concatenated together, so no document separators are needed.""")

    def check_source_file(self, fname):
        # Generic nits related to various source files

        with open(os.path.join(GIT_TOP, fname), encoding="utf-8") as f:
            contents = f.read()

        if not contents.endswith("\n"):
            self.failure(f"Missing newline at end of '{fname}'. Check your text "
                         f"editor settings.")

        if contents.startswith("\n"):
            self.failure(f"Please remove blank lines at start of '{fname}'")

        if contents.endswith("\n\n"):
            self.failure(f"Please remove blank lines at end of '{fname}'")


class GitDiffCheck(ComplianceTest):
    """
    Checks for conflict markers or whitespace errors with git diff --check
    """
    name = "GitDiffCheck"
    doc = "Git conflict markers and whitespace errors are not allowed in added changes"
    path_hint = "<git-top>"

    def run(self):
        offending_lines = []
        # Use regex to filter out unnecessay output
        # Reason: `--check` is mutually exclusive with `--name-only` and `-s`
        p = re.compile(r"\S+\: .*\.")

        for shaidx in get_shas(COMMIT_RANGE):
            # Ignore non-zero return status code
            # Reason: `git diff --check` sets the return code to the number of offending lines
            diff = git("diff", f"{shaidx}^!", "--check", ignore_non_zero=True)

            lines = p.findall(diff)
            lines = map(lambda x: f"{shaidx}: {x}", lines)
            offending_lines.extend(lines)

        if len(offending_lines) > 0:
            self.failure("\n".join(offending_lines))


class GitLint(ComplianceTest):
    """
    Runs gitlint on the commits and finds issues with style and syntax

    """
    name = "Gitlint"
    doc = "See https://docs.zephyrproject.org/latest/contribute/guidelines.html#commit-guidelines for more details"
    path_hint = "<git-top>"

    def run(self):
        # By default gitlint looks for .gitlint configuration only in
        # the current directory
        try:
            subprocess.run('gitlint --commits ' + COMMIT_RANGE,
                           check=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           shell=True, cwd=GIT_TOP)

        except subprocess.CalledProcessError as ex:
            self.failure(ex.output.decode("utf-8"))


class PyLint(ComplianceTest):
    """
    Runs pylint on all .py files, with a limited set of checks enabled. The
    configuration is in the pylintrc file.
    """
    name = "Pylint"
    doc = "See https://www.pylint.org/ for more details"
    path_hint = "<git-top>"

    def run(self):
        # Path to pylint configuration file
        pylintrc = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "pylintrc"))

        # Path to additional pylint check scripts
        check_script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                        "../pylint/checkers"))

        # List of files added/modified by the commit(s).
        files = get_files(filter="d")

        # Filter out everything but Python files. Keep filenames
        # relative (to GIT_TOP) to stay farther from any command line
        # limit.
        py_files = filter_py(GIT_TOP, files)
        if not py_files:
            return

        python_environment = os.environ.copy()
        if "PYTHONPATH" in python_environment:
            python_environment["PYTHONPATH"] = check_script_dir + ":" + \
                                               python_environment["PYTHONPATH"]
        else:
            python_environment["PYTHONPATH"] = check_script_dir

        pylintcmd = ["pylint", "--output-format=json2", "--rcfile=" + pylintrc,
                     "--load-plugins=argparse-checker"] + py_files
        logger.info(cmd2str(pylintcmd))
        try:
            subprocess.run(pylintcmd,
                           check=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           cwd=GIT_TOP,
                           env=python_environment)
        except subprocess.CalledProcessError as ex:
            output = ex.output.decode("utf-8")
            messages = json.loads(output)['messages']
            for m in messages:
                severity = 'unknown'
                if m['messageId'][0] in ('F', 'E'):
                    severity = 'error'
                elif m['messageId'][0] in ('W','C', 'R', 'I'):
                    severity = 'warning'
                self.fmtd_failure(severity, m['messageId'], m['path'],
                                  m['line'], col=str(m['column']), desc=m['message']
                                  + f" ({m['symbol']})")

            if len(messages) == 0:
                # If there are no specific messages add the whole output as a failure
                self.failure(output)


def filter_py(root, fnames):
    # PyLint check helper. Returns all Python script filenames among the
    # filenames in 'fnames', relative to directory 'root'.
    #
    # Uses the python-magic library, so that we can detect Python
    # files that don't end in .py as well. python-magic is a frontend
    # to libmagic, which is also used by 'file'.
    return [fname for fname in fnames
            if (fname.endswith(".py") or
             magic.from_file(os.path.join(root, fname),
                             mime=True) == "text/x-python")]


class Identity(ComplianceTest):
    """
    Checks if Emails of author and signed-off messages are consistent.
    """
    name = "Identity"
    doc = "See https://docs.zephyrproject.org/latest/contribute/guidelines.html#commit-guidelines for more details"
    # git rev-list and git log don't depend on the current (sub)directory
    # unless explicited
    path_hint = "<git-top>"

    def run(self):
        for shaidx in get_shas(COMMIT_RANGE):
            commit = git("log", "--decorate=short", "-n 1", shaidx)
            signed = []
            author = ""
            sha = ""
            parsed_addr = None
            for line in commit.split("\n"):
                match = re.search(r"^commit\s([^\s]*)", line)
                if match:
                    sha = match.group(1)
                match = re.search(r"^Author:\s(.*)", line)
                if match:
                    author = match.group(1)
                    parsed_addr = parseaddr(author)
                match = re.search(r"signed-off-by:\s(.*)", line, re.IGNORECASE)
                if match:
                    signed.append(match.group(1))

            error1 = f"{sha}: author email ({author}) needs to match one of " \
                     f"the signed-off-by entries."
            error2 = f"{sha}: author email ({author}) does not follow the " \
                     f"syntax: First Last <email>."
            error3 = f"{sha}: author email ({author}) must be a real email " \
                     f"and cannot end in @users.noreply.github.com"
            failure = None
            if author not in signed:
                failure = error1

            if not parsed_addr or len(parsed_addr[0].split(" ")) < 2:
                if not failure:

                    failure = error2
                else:
                    failure = failure + "\n" + error2
            elif parsed_addr[1].endswith("@users.noreply.github.com"):
                failure = error3

            if failure:
                self.failure(failure)


class BinaryFiles(ComplianceTest):
    """
    Check that the diff contains no binary files.
    """
    name = "BinaryFiles"
    doc = "No binary files allowed."
    path_hint = "<git-top>"

    def run(self):
        BINARY_ALLOW_PATHS = ("doc/", "boards/", "samples/", "server/django/staticfiles/img/")
        # svg files are always detected as binary, see .gitattributes
        BINARY_ALLOW_EXT = (".jpg", ".jpeg", ".png", ".svg", ".webp")

        for stat in git("diff", "--numstat", "--diff-filter=A",
                        COMMIT_RANGE).splitlines():
            added, deleted, fname = stat.split("\t")
            if added == "-" and deleted == "-":
                if (fname.startswith(BINARY_ALLOW_PATHS) and
                    fname.endswith(BINARY_ALLOW_EXT)):
                    continue
                self.failure(f"Binary file not allowed: {fname}")


class ImageSize(ComplianceTest):
    """
    Check that any added image is limited in size.
    """
    name = "ImageSize"
    doc = "Check the size of image files."
    path_hint = "<git-top>"

    def run(self):
        SIZE_LIMIT = 250 << 10
        BOARD_SIZE_LIMIT = 100 << 10

        for file in get_files(filter="d"):
            full_path = os.path.join(GIT_TOP, file)
            mime_type = magic.from_file(full_path, mime=True)

            if not mime_type.startswith("image/"):
                continue

            size = os.path.getsize(full_path)

            limit = SIZE_LIMIT
            if file.startswith("boards/"):
                limit = BOARD_SIZE_LIMIT

            if size > limit:
                self.failure(f"Image file too large: {file} reduce size to "
                             f"less than {limit >> 10}kB")


def init_logs(cli_arg):
    # Initializes logging

    global logger

    level = os.environ.get('LOG_LEVEL', "WARN")

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(levelname)-8s: %(message)s'))

    logger = logging.getLogger('')
    logger.addHandler(console)
    logger.setLevel(cli_arg or level)

    logger.info("Log init completed, level=%s",
                 logging.getLevelName(logger.getEffectiveLevel()))


def inheritors(klass):
    subclasses = set()
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


def annotate(res):
    """
    https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#about-workflow-commands
    """
    notice = f'::{res.severity} file={res.file}' + \
             (f',line={res.line}' if res.line else '') + \
             (f',col={res.col}' if res.col else '') + \
             f',title={res.title}::{res.message}'
    print(notice)


def resolve_path_hint(hint):
    if hint == "<zephyr-base>":
        return ZEPHYR_BASE
    elif hint == "<git-top>":
        return GIT_TOP
    else:
        return hint


def parse_args(argv):

    default_range = 'main..HEAD'
    parser = argparse.ArgumentParser(
        description="Check for coding style and documentation warnings.", allow_abbrev=False)
    parser.add_argument('-c', '--commits', default=default_range,
                        help=f'''Commit range in the form: a..[b], default is
                        {default_range}''')
    parser.add_argument('-o', '--output', default="compliance.xml",
                        help='''Name of outfile in JUnit format,
                        default is ./compliance.xml''')
    parser.add_argument('-n', '--no-case-output', action="store_true",
                        help="Do not store the individual test case output.")
    parser.add_argument('-l', '--list', action="store_true",
                        help="List all checks and exit")
    parser.add_argument("-v", "--loglevel", choices=['DEBUG', 'INFO', 'WARNING',
                                                     'ERROR', 'CRITICAL'],
                        help="python logging level")
    parser.add_argument('-m', '--module', action="append", default=[],
                        help="Checks to run. All checks by default. (case " \
                        "insensitive)")
    parser.add_argument('-e', '--exclude-module', action="append", default=[],
                        help="Do not run the specified checks (case " \
                        "insensitive)")
    parser.add_argument('-j', '--previous-run', default=None,
                        help='''Pre-load JUnit results in XML format
                        from a previous run and combine with new results.''')
    parser.add_argument('--annotate', action="store_true",
                        help="Print GitHub Actions-compatible annotations.")

    return parser.parse_args(argv)

def _main(args):
    # The "real" main(), which is wrapped to catch exceptions and report them
    # to GitHub. Returns the number of test failures.

    global ZEPHYR_BASE
    ZEPHYR_BASE = os.environ.get('ZEPHYR_BASE')
    if not ZEPHYR_BASE:
        # Let the user run this script as ./scripts/ci/check_compliance.py without
        #  making them set ZEPHYR_BASE.
        ZEPHYR_BASE = str(Path(__file__).resolve().parents[2])

        # Propagate this decision to child processes.
        os.environ['ZEPHYR_BASE'] = ZEPHYR_BASE

    # The absolute path of the top-level git directory. Initialize it here so
    # that issues running Git can be reported to GitHub.
    global GIT_TOP
    GIT_TOP = git("rev-parse", "--show-toplevel")

    # The commit range passed in --commit, e.g. "HEAD~3"
    global COMMIT_RANGE
    COMMIT_RANGE = args.commits

    init_logs(args.loglevel)

    logger.info(f'Running tests on commit range {COMMIT_RANGE}')

    if args.list:
        for testcase in inheritors(ComplianceTest):
            print(testcase.name)
        return 0

    # Load saved test results from an earlier run, if requested
    if args.previous_run:
        if not os.path.exists(args.previous_run):
            # This probably means that an earlier pass had an internal error
            # (the script is currently run multiple times by the ci-pipelines
            # repo). Since that earlier pass might've posted an error to
            # GitHub, avoid generating a GitHub comment here, by avoiding
            # sys.exit() (which gets caught in main()).
            print(f"error: '{args.previous_run}' not found",
                  file=sys.stderr)
            return 1

        logging.info(f"Loading previous results from {args.previous_run}")
        for loaded_suite in JUnitXml.fromfile(args.previous_run):
            suite = loaded_suite
            break
    else:
        suite = TestSuite("Compliance")

    included = list(map(lambda x: x.lower(), args.module))
    excluded = list(map(lambda x: x.lower(), args.exclude_module))

    for testcase in inheritors(ComplianceTest):
        # "Modules" and "testcases" are the same thing. Better flags would have
        # been --tests and --exclude-tests or the like, but it's awkward to
        # change now.

        if included and testcase.name.lower() not in included:
            continue

        if testcase.name.lower() in excluded:
            print("Skipping " + testcase.name)
            continue

        test = testcase()
        try:
            print(f"Running {test.name:16} tests in "
                  f"{resolve_path_hint(test.path_hint)} ...")
            test.run()
        except EndTest:
            pass

        # Annotate if required
        if args.annotate:
            for res in test.fmtd_failures:
                annotate(res)

        suite.add_testcase(test.case)

    if args.output:
        xml = JUnitXml()
        xml.add_testsuite(suite)
        xml.update_statistics()
        xml.write(args.output, pretty=True)

    failed_cases = []
    name2doc = {testcase.name: testcase.doc
                for testcase in inheritors(ComplianceTest)}

    for case in suite:
        if case.result:
            if case.is_skipped:
                logging.warning(f"Skipped {case.name}")
            else:
                failed_cases.append(case)
        else:
            # Some checks like codeowners can produce no .result
            logging.info(f"No JUnit result for {case.name}")

    n_fails = len(failed_cases)

    if n_fails:
        print(f"{n_fails} checks failed")
        for case in failed_cases:
            for res in case.result:
                errmsg = res.text.strip()
                logging.error(f"Test {case.name} failed: \n{errmsg}")
            if args.no_case_output:
                continue
            with open(f"{case.name}.txt", "w") as f:
                docs = name2doc.get(case.name)
                f.write(f"{docs}\n")
                for res in case.result:
                    errmsg = res.text.strip()
                    f.write(f'\n {errmsg}')

    if args.output:
        print(f"\nComplete results in {args.output}")
    return n_fails


def main(argv=None):
    args = parse_args(argv)

    try:
        # pylint: disable=unused-import
        from lxml import etree
    except ImportError:
        print("\nERROR: Python module lxml not installed, unable to proceed")
        print("See https://github.com/weiwei/junitparser/issues/99")
        return 1

    try:
        n_fails = _main(args)
    except BaseException:
        # Catch BaseException instead of Exception to include stuff like
        # SystemExit (raised by sys.exit())
        print(f"Python exception in `{__file__}`:\n\n"
              f"```\n{traceback.format_exc()}\n```")

        raise

    sys.exit(n_fails)


def cmd2str(cmd):
    # Formats the command-line arguments in the iterable 'cmd' into a string,
    # for error messages and the like

    return " ".join(shlex.quote(word) for word in cmd)


def err(msg):
    cmd = sys.argv[0]  # Empty if missing
    if cmd:
        cmd += ": "
    sys.exit(f"{cmd} error: {msg}")


if __name__ == "__main__":
    main(sys.argv[1:])
