###############################################################################
#
#   Copyright 2016 Michele Filannino
#
#   Derivated from Christopher Kotfila's i2b2 evaluation scripts:
#       https://github.com/kotfic/i2b2_evaluation_scripts
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#
# 2016 CEGS N-GRID Evaluation Scripts
#
# This script is distributed as apart of the 2016 CEGS N-GRID Shared tasks.
# It is intended to be used via command line:
#
# $> python evaluate.py [FLAGS] GOLD SYSTEM
#
#   It produces Precision, Recall and F1 (P/R/F1) measure for the PHI task.
# SYSTEM and GOLD may be individual files representing system output in the
# case of SYSTEM and the gold standard in the case of GOLD.  SYSTEM and GOLD
# may also be directories in which case all files in SYSTEM will be compared
# to files the GOLD directory based on their file names. File names MUST be of
# the form: XXX-YY.xml where XXX is the patient id,  and YY is the document id.
# See the README.md file for more details.
#
# Basic Flags:
# -v, --verbose :: Print document by document P/R/F1 for each document instead
#                  of summary statistics for an entire set of documents.
#
# Basic Examples:
#
# $> python evaluate.py gold/ system/
#
#   Evaluate the set of system outputs in the folder system against the set of
# gold standard annotations in gold/ .
#
#
#
# Advanced Usage:
#
#   Some additional functionality is made available for testing and error
# analysis. This functionality is provided AS IS with the hopes that it will
# be useful. It should be considered 'experimental' at best, may be bug prone
# and will not be explicitly supported, though, bug reports and pull requests
# are welcome.
#
# Advanced Flags:
#
# --filter [TAG ATTRIBUTES] :: run P/R/F1 measures in either summary or verbose
#                              mode (see -v) for the list of attributes defined
#                              by TAG ATTRIBUTES. This may be a comma separated
#                              list of tag names and attribute values. For more
#                              see Advanced Examples.
# --conjunctive :: If multiple values are passed to filter as a comma separated
#                  list, treat them as a series of AND based filters instead of
#                  a series of OR based filters
# --invert :: run P/R/F1 on the inverted set of tags defined by TAG ATTRIBUTES
#             in the --filter tag (see --filter).
#
# Advanced Examples:
#
# $> python evaluate.py cr --filter MEDICATION gold/ system/
#
#   Evaluate system output in system/ folder against gold/ folder considering
# only MEDICATION tags
#
# $> python evaluate.py cr --filter CAD,OBESE gold/ system/
#
#   Evaluate system output in system/ folder against gold/ folder considering
# only CAD or OBESE tags. Comma separated lists to the --filter flag are con-
# joined via OR.
#
# $> python evaluate.py cr --filter "CAD,before DCT" gold/ system/
#
#   Evaluate system output in system/ folder against gold/ folder considering
# only CAD *OR* tags with a time attribute of before DCT. This is probably
# not what you want when filtering, see the next example
#
# $> python evaluate.py cr --conjunctive \
#                          --filter "CAD,before DCT" gold/ system/
#
#   Evaluate system output in system/ folder against gold/ folder considering
# CAD tags *AND* tags with a time attribute of before DCT.
#
# $> python evaluate.py cr --invert \
#                          --filter MEDICATION gold/ system/
#
#  Evaluate system output in system/ folder against gold/ folder considering
# any tag which is NOT a MEDICATION tag.
#
# $> python evaluate.py cr --invert \
#                          --conjunctive \
#                          --filter "CAD,before DCT" gold/ system/
#
#  Evaluate system output in system/ folder against gold/ folder considering
# any tag which is NOT CAD and with a time attribute of 'before DCT'


import argparse
from collections import defaultdict
import glob
import os
import xml.etree.cElementTree as etree
import warnings

import numpy as np
from scipy.stats import wilcoxon

from classes import StandoffAnnotation
from classes import Evaluate
from classes import CombinedEvaluation
from classes import PHITrackEvaluation
from tags import PHITag


# This function is 'exterimental' as in it works for my use cases
# But is not generally well documented or a part of the expected
# workflow.
def get_predicate_function(arg, tag):
    """ This function takes a tag attribute value, determines the attribute(s)
    of the class(es) this value belongs to,  and then returns a predicate
    function that returns true if this value is set for the  calculated
    attribute(s) on the class(es). This allows for overlap - ie. "ACE
    Inhibitor" is a valid type1 and a valid type2 attribute value.  If arg
    equals "ACE Inhibitor" our returned predicate function will return true if
    our tag has "ACE Inhibitor" set for either type1 or type2 attributes.
    Currently this is implemented to ONLY work with MEDICAL_TAG_CLASSES but
    could be easily extended to work with PHI tag classes.
    """
    attrs = []

    # Get a list of valid attributes for this argument
    # If we have a tag name (ie. MEDICATION) add 'name' to the attributes
    if arg in tag.tag_types.keys():
        attrs.append("name")
    else:
        tag_attributes = ["valid_type1", "valid_type2", "valid_indicator",
                          "valid_status", "valid_time", "valid_type"]
        for cls in MEDICAL_TAG_CLASSES:
            for attr in tag_attributes:
                try:
                    if arg in getattr(cls, attr):
                        # add the attribute,  strip out the "valid_" prefix
                        # This assumes that classes follow the
                        # valid_ATTRIBUTE convention
                        # and will break if they are extended
                        attrs.append(attr.replace("valid_", ""))
                except AttributeError:
                    continue
        # Delete these so we don't end up carrying around
        # references in our function
        try:
            del tag_attributes
            del cls
            del attr
        except NameError:
            pass

    attrs = list(set(attrs))

    if len(attrs) == 0:
        print("WARNING: could not find valid class attribute for " +
              "\"{}\", + skipping.".format(arg))
        return lambda t: True

    # Define the predicate function we will use. artrs are scoped into
    # the closure,  which is sort of the whole point of the
    # get_predicate_function function.
    def matchp(t):
        for attr in attrs:
            if attr == "name" and t.name == arg:
                return True
            else:
                try:
                    if getattr(t, attr).lower() == arg.lower():
                        return True
                except (AttributeError, KeyError):
                    pass
        return False

    return matchp


def get_document_dict_by_system_id(system_dirs):
    """Takes a list of directories and returns all of the StandoffAnnotation's
    as a system id, annotation id indexed dictionary. System id (or
    StandoffAnnotation.sys_id) is whatever values trail the XXX-YY file id.
    For example:
       301-01foo.xml
       patient id:   301
       document id:  01
       system id:    foo

    In the case where there is nothing trailing the document id,  the sys_id
    is the empty string ('').
    """
    documents = defaultdict(lambda: defaultdict(int))

    for d in system_dirs:
        for fn in os.listdir(d):
            # Only look at xml files
            if fn.endswith("xml"):
                sa = StandoffAnnotation(d + fn)
                documents[sa.sys_id][sa.id] = sa

    return documents


def evaluate(system, gs, eval_class, **kwargs):
    """Evaluate the system by calling the eval_class (either EvaluatePHI or
    EvaluateCardiacRisk classes) with an annotation id indexed dict of
    StandoffAnnotation classes for the system(s) and the gold standard outputs.
    'system' will be a list containing either one file,  or one or more
    directories. 'gs' will be a file or a directory.  This function mostly just
    handles formatting arguments for the eval_class.
    """
    assert issubclass(eval_class, Evaluate) or \
        issubclass(eval_class, CombinedEvaluation), \
        "Must pass in EvaluatePHI or EvaluateCardiacRisk classes to evaluate()"

    gold_sa = {}
    evaluations = []

    # Strip verbose keyword if it exists
    # verbose is not a keyword to our eval classes
    # __init__() functions
    try:
        verbose = kwargs['verbose']
        del kwargs['verbose']
    except KeyError:
        verbose = False

    assert os.path.exists(gs), "{} does not exist!".format(gs)

    for s in system:
        assert os.path.exists(s), "{} does not exist!".format(s)


    # Handle if two files were passed on the command line
    if os.path.isfile(system[0]) and os.path.isfile(gs):
        gs = StandoffAnnotation(gs)
        s = StandoffAnnotation(system[0])
        e = eval_class({s.id: s}, {gs.id: gs}, **kwargs)
        e.print_docs()
        evaluations.append(e)

    # Handle the case where 'gs' is a directory and 'system' is a
    # list of directories.  For individual evaluation (one system output
    #  against the gold standard) this is a little overkill,  but this
    # lets us run multiple systems against the gold standard and get numbers
    # for each system output. useful for annotator agreement and final system
    # evaluations. Error checking to ensure consistent files in each directory
    # will be handled by the evaluation class.
    elif all([os.path.isdir(s) for s in system]) and os.path.isdir(gs):
        # Get a dict of gold standoff annotation indexed by id
        for fn in os.listdir(gs):
            sa = StandoffAnnotation(gs + fn)
            gold_sa[sa.id] = sa

        for s_id, system_sa in get_document_dict_by_system_id(system).items():
            e = eval_class(system_sa, gold_sa, **kwargs)
            e.print_report(verbose=verbose)
            evaluations.append(e)

    else:
        Exception("Must pass file.xml file.xml  or [directory/]+ directory/"
                  "on command line!")

    return evaluations[0] if len(evaluations) == 1 else evaluations


def evaluate_rdoc(gold_fld, syst_fld, verbose=False):
    """Evaluates the system's predictions wrt the gold ones.

    Both sources must be in a separate folder.
    """

    wrong_severity_value = Exception('Unexpected severity value')
    diff_folders_content = Exception('Folders must contain the same XML files')
    level2score = {'ABSENT': 0, 'MILD': 1, 'MODERATE': 2, 'SEVERE': 3}
    score2level = {a: b for b, a in level2score.items()}

    def get_prediction(file_path):
        """It returns the positive valence severity score from an XML document.
        """
        source = etree.parse(file_path)
        score = source.findall('./TAGS/POSITIVE_VALENCE')[0].attrib['score']
        score = score.upper().strip()
        if score in level2score.keys():
            return level2score[score]
        else:
            print 'ERROR: {} contains an invalid severity score ({})'.format(
                file_path, score)
            raise wrong_severity_value

    def mean_absolute_error(gold, system):
        gold, system = np.array(gold), np.array(system)
        output_errors = np.average(np.abs(system - gold))
        return output_errors

    def compute_score(x, y):
        """It computes the Macro-averaged Mean Absolute Error (MAE), normalize
        it wrt the highest possible error and convert it into a percentage
        score. The score ranges between 0 and 1:
         - 000: lowest score;
         - 100: highest score;
        """
        mae_per_score = []
        stats_per_score = dict()
        for score in set(x):
            result = 0

            # Filters gold and system, by looking at gold's elements.
            x_n, y_n = zip(*[(a, b) for a, b in zip(x, y) if a == score])

            # According to the gold standard, I compute the sum of the maximum
            # error for each prediction.
            # In a scale (0, 1, 2, 3), the points 1 and 2 can lead to maximum
            # error 2. The points 0 and 3 can lead to maximum error 3.
            if score in (0, 3):
                normalisation_factor = 3
            else:
                normalisation_factor = 2
            # Compute micro-averaged MAE
            try:
                result = 100 * (1 - (mean_absolute_error(x_n, y_n) / \
                                     normalisation_factor))
            except ValueError:
                # The system hasn't predicted anything with this score!
                result = 0

            mae_per_score.append(result)
            stats_per_score[score] = (len(x_n),
                                      y.count(score),
                                      result)
        score = sum(mae_per_score) / len(set(x))
        return stats_per_score, score

    golds = set([os.path.basename(x) for x in glob.glob(gold_fld + '/*.xml')])
    systs = set([os.path.basename(x) for x in glob.glob(syst_fld + '/*.xml')])
    if golds != systs:
        print 'ERROR: Folders must contain the same XML files.'
        raise diff_folders_content

    X = [get_prediction(f) for f in sorted(glob.glob(gold_fld + '/*.xml'))]
    Y = [get_prediction(f) for f in sorted(glob.glob(syst_fld + '/*.xml'))]

    stats, score = compute_score(X, Y)
    print
    print 'CLASSES    ( support )  '
    print '           (gold|syst): '
    print '--------------------------------'
    for value in sorted(stats.keys()):
        print '{:10s} ({:>4d}|{:>4d}): {:>07.4f}%'.format(
            score2level[value].lower(), *stats[value])
    print '--------------------------------'
    print 'SCORE      ({:>4d}|{:>4d}): {:>07.4f}%'.format(
        len(X), len(Y), score)

    error_bar = lambda x, y: '*' * np.absolute(x - y)

    if verbose:
        print
        print
        print '{:<12s} {:^6s} {:^6s}   {:<6s}'.format('RECORD NAME', 'GOLD',
                                                      'SYSTEM', 'ERROR')
        for pos, f in enumerate(sorted(glob.glob(gold_fld + '/*.xml'))):
            print '{:<12s} {:^6d} {:^6d}   {:<6s}'.format(
                os.path.basename(f), X[pos], Y[pos], error_bar(X[pos], Y[pos]))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            print 'Wilcoxon Signed-Rank test p-value: {:>07.7f}'.format(
                wilcoxon(X, Y)[1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="To Write")

    subparsers = parser.add_subparsers(dest='track', help='sub-command help')

    oneb_parser = subparsers.add_parser('track1',
                                        help='Evaluation script for Track 1.B')
    oneb_parser.add_argument('--filter',
                             help="Filters to apply, use with invert & conjunction")
    oneb_parser.add_argument('--conjunctive',
                             help="if multiple filters are applied, should these be combined with 'and' or 'or'",
                             action="store_true")
    oneb_parser.add_argument('--invert',
                             help="Invert the list of filters,  match only tags that do not match filter functions",
                             action="store_true")
    oneb_parser.add_argument('-v', '--verbose',
                             help="list full document by document scores",
                             action="store_true")
    oneb_parser.add_argument("from_dir",
                             help="directories to pull documents from")
    oneb_parser.add_argument("to_dir",
                             help="directories to save documents to")

    two_parser = subparsers.add_parser('track2',
                                       help='Evaluation script for Track 2')
    two_parser.add_argument('-v', '--verbose',
                            help="print more information",
                            action="store_true")
    two_parser.add_argument("gold_dir",
                            help="gold directory")
    two_parser.add_argument("syst_dir",
                            help="system directory")

    args = parser.parse_args()

    if args.track == 'track1':
        if args.filter:
            evaluate([args.to_dir], args.from_dir,
                     PHITrackEvaluation,
                     verbose=args.verbose,
                     invert=args.invert,
                     conjunctive=args.conjunctive,
                     filters=[get_predicate_function(a, PHITag)
                              for a in args.filter.split(",")])
        else:
            evaluate([args.to_dir], args.from_dir, PHITrackEvaluation,
                     verbose=args.verbose)
    else:
        evaluate_rdoc(os.path.abspath(args.gold_dir),
                      os.path.abspath(args.syst_dir), verbose=args.verbose)
