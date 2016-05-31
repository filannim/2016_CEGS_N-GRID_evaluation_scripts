# 2016 CEGS N-GRID Shared Tasks Evaluation Scripts

This script is distributed as a part of the 2016 CEGS N-GRID tasks. 

If you would like to contribute to this project, pull requests are welcome.
Please see: [here](https://help.github.com/articles/fork-a-repo) for instructions
on how to make a fork of this repository, and
[here](https://help.github.com/articles/using-pull-requests) for instructions
on making a pull request. Suggestions for improvements, bugs or feature
requests may be directed to the 2016 CEGS N-GRID evaluation scripts' [issues
page](https://github.com/filannim/2016_CEGS_N-GRID_evaluation_scripts/issues)






## Setup

This script also requires the following Python packages:
lxml version 3.3.1
numpy version 1.8.0

If you get an error when running the script, please make sure that these
are installed and accessible to your Python installation.






## Running the script

This script is intended to be used via command line:
```shell
$ python evaluate.py [track1|track2] [FLAGS] GOLD SYSTEM
```

It produces performance scores for Track 1 (de-identification) and Track 2 (RDoC classification).
SYSTEM and GOLD may be directories or single files according to the track you are running.
See below for more information on the different outputs.






## Output for Track 1.B: De-identification

To compare your system output for the de-identification track, run the following 
command on individual files:
```shell
$ python evaluate.py track1 {gold.xml} {system.xml}
```
(replace the file names in {}s with the names of your actual files)

or, to run the script on directories of files:
```shell
$ python evaluate.py track1 {gold}/ {system}/
```
(again, replace the folder names in {}s with the names of your actual folders)

Running one of these versions wil produce output that looks like this:

```
Strict (521)             Measure        Macro (SD)     Micro               
---------------------------------------------------------------------------
Total                    Precision      0.6635 (0.11)  0.6537              
                         Recall         0.4906 (0.12)  0.4988              
                         F1             0.5641         0.5658              


Relaxed (521)            Measure        Macro (SD)     Micro               
---------------------------------------------------------------------------
Total                    Precision      0.8970 (0.086) 0.9047              
                         Recall         0.6663 (0.15)  0.6903              
                         F1             0.7646         0.7831              


HIPAA Strict (521)       Measure        Macro (SD)     Micro               
---------------------------------------------------------------------------
Total                    Precision      0.7406 (0.098) 0.7225              
                         Recall         0.7406 (0.098) 0.7225              
                         F1             0.7406         0.7225              


HIPAA Relaxed (521)      Measure        Macro (SD)     Micro               
---------------------------------------------------------------------------
Total                    Precision      1.0 (0.0)      1.0                 
                         Recall         1.0 (0.0)      1.0                 
                         F1             1.0            1.0                 
```

A few notes to explain this output:
- The "(521)" represents the number of files the script was run on.
- "Strict" evaluations require that the offsets for the system outputs match *exactly*.
- "Relaxed" evaluations allow for the "end" part of the offsets to be off by
2--this allows for variations in including "'s" and other endings that many
systems will ignore due to tokenization.
- "HIPPA" evalutions include only the tags from a strict interpretation of the
HIPAA guidelines. See the below list for which tags are included in this
evaluation.



### HIPAA-compliant PHI

- NAME/PATIENT
- AGE
- LOCATION/CITY
- LOCATION/STREET
- LOCATION/ZIP
- LOCATION/ORGANIZATION
- DATE
- CONTACT/PHONE
- CONTACT/FAX
- CONTACT/EMAIL
- ID/SSN
- ID/MEDICALRECORD
- ID/HEALTHPLAN
- ID/ACCOUNT
- ID/LICENSE
- ID/VEHICLE
- ID/DEVICE
- ID/BIOID
- ID/IDNUM 


### Verbose flag

To get document-by-document information about the accuracy of your tags, you
can use the "-v" or "--verbose" flag. For example:
```shell
$ python evaluate.py track1 -v {gold}/ {system}/
```

### Advanced usage

Some additional functionality is made available for testing and error 
analysis. This functionality is provided AS IS with the hopes that it will
be useful. It should be considered 'experimental' at best, may be bug prone
and will not be explicitly supported, though, bug reports and pull requests
are welcome.

Advanced Flags:

--filter [TAG ATTRIBUTES] :: run P/R/F1 measures in either summary or verbose
                             mode (see -v) for the list of attributes defined
                             by TAG ATTRIBUTES. This may be a comma separated
                             list of tag names and attribute values. For more
                             see Advanced Examples.
--conjunctive :: If multiple values are passed to filter as a comma separated
                 list, treat them as a series of AND based filters instead of
                 a series of OR based filters
--invert :: run P/R/F1 on the inverted set of tags defined by TAG ATTRIBUTES
            in the --filter tag (see --filter).

Advanced Examples:

```shell
$ python evaluate.py track1 --filter LOCATION gold/ system/
```
Evaluate system output in system/ folder against gold/ folder considering
only LOCATION tags

```shell
$ python evaluate.py track1 --filter LOCATION,ID gold/ system/
```
Evaluate system output in system/ folder against gold/ folder considering
only LOCATION or ID tags. Comma separated lists to the --filter flag are con-
joined via OR.

```shell
$ python evaluate.py track1 --invert --filter LOCATION gold/ system/
```
Evaluate system output in system/ folder against gold/ folder considering
any tag which is NOT a LOCATION tag.






## Output for the Track 2: RDoC classification

To compare your system output for the RDoC track, run the following command on
the folders:
```shell
$ python evaluate.py track2 {gold}/ {system}/
```
(again, replace the folder names in {}s with the names of your actual folders)

Running one of these versions wil produce output that looks like this:

```
CLASSES    ( support )
           (gold|syst):
--------------------------------
absent     (   3|   2): 85.1852%
mild       (   3|   3): 83.3333%
moderate   (   2|   2): 87.5000%
severe     (   2|   3): 91.6667%
--------------------------------
SCORE      (  10|  10): 86.9213%
```

A few notes to explain this output:
- The numbers in rounded brakets "absent    (   3|   2)" represent the support.
They refer to the number of records annotated as ABSENT in the GOLD and SYSTEM
folder respectively.
- The percentage number corresponding to a class row is the normalised
micro-averaged mean absolute error (per class).
- The last row (SCORE) is the one used for the final ranking and it's the
macro-averaged mean absolute error.


### Verbose flag

To get document-by-document information about the performance of your method,
you can use the "-v" or "--verbose" flag. For example:

```shell
$ python evaluate.py track2 -v {gold}/ {system}/
```

This command append the following output to the default one:

```
RECORD NAME   GOLD  SYSTEM   ERROR
1239_gs.xml    2      2
1412_gs.xml    0      3      ***
1418_gs.xml    1      0      *
1421_gs.xml    2      1      *
1470_gs.xml    3      2      *
3322_gs.xml    0      1      *
3325_gs.xml    1      1
3386_gs.xml    0      0
4423_gs.xml    1      3      **
6427_gs.xml    3      3
```

The column GOLD and SYSTEM represent the numerical value corresponding to the 
severity level according to the following mapping:
- 0 -> ABSENT
- 1 -> MILD
- 2 -> MODERATE
- 3 -> SEVERE

The last column (ERROR) depicts the gravity of the error.