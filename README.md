# WhenInRome

> "When in Rome, do as the Romans do." -- St. Augustine

When in a new code, follow the formatting of that code.

This script detects clang-format settings to be used when touching a new code. Give one or more source files, it tries to repeatedly run clang-format with different settings to find the settings that best match the input source files.

## Usage

```
python3 WhenInRome.py <source_files>
```

The script utilizes a `formatting-options.yml` describing all the options that need to be tried, and the order in which they need to be tried. Although we provide a `formatting-options.yml` file, for best results this file may require more tweaking.

The script utilizes a temporary folder (by default `./tmp/`) to write temporary data into. This can serve multiple purposes:
* keep a cache of what's being run so that subsequent runs are faster
* allow the user to inspect various results of intermediate steps

If the user provides multiple source files, they will be combined into one source file before performing the experiments. Certain formatting options might be affected (e.g., the ones related to includes). Using too many files would increase the accuracy, but will also increase the running time for the script.

Depending on the input, the script can take several minutes to complete.

## Details on formatting options

The [formatting-options.yml](formatting-options.yml) file is used to direct the search for the best matching style. This is a YAML file describing all the clang-format style options to be set, and the values that these options.

### Iterations

The file should contain a list of options. Each option will indicate a new iteration for the matching process. Iterations will be based on the values found in the previous iterations. Let us take an example:

```
Opt1: [val1_A, val1_B, val1_C]
Opt2: [val2_X, val2_Y, val2_Z]
Opt3: [val3_K, val3_L, val3_M]
```

Assuming, that the best matching options would be: `val1_B`, `val2_X` and `val3_M`, then the 3 iterations would do the following:
1. without any precondition, find the best matching between the following alternatives:
    * `Opt1: val1_A`
    * `Opt1: val1_B`
    * `Opt1: val1_C`
2. with `Opt1: val1_B` as precondition, find the best matching between the following alternatives:
    * `Opt2: val2_X`
    * `Opt2: val2_Y`
    * `Opt2: val2_Z`
3. with `Opt1: val1_B` and `Opt2: val2_X` as preconditions, find the best matching between the following alternatives:
    * `Opt3: val3_K`
    * `Opt3: val3_L`
    * `Opt3: val3_M`

We do it like this, to avoid the NP-completeness of the problem.

The script will do the experimenting for all the iterations, and the result of the last iteration will be the result of the script. It contains (probably) the best combination of clang-format options that minimize the error between the formatted code and the original code.

### Choosing the best variant

At each iteration, the script uses `diff` to check the differences between the formatted code and the original code. The goal of the script is to minimize the number of lines different between the formatted code and the original source code.

All the formatted files, their diffs and the corresponding `.clang-format` file is kept in the temporary directory, allowing the user to manually inspect them.

Sometimes, the best option is implicit (i.e., defined by the base-style). In this case, the script will ignore the setting, and not add it to the list of options to be applied to clang-format.

### The syntax of an option

Each option contains the following:
* a name for the option
* a set of values that need to be tried

For most of the options, we can encode this in a simple way, as a key-to-list entry. Examples:
```
- NamespaceIndentation: [None, Inner, All]
- BreakBeforeBraces: [Attach, Linux, Mozilla, Stroustrup, Allman, GNU, WebKit]
- SpacesInParentheses: [true, false]
```

These entries correspond to the style options of clang-format.

There are however cases in which we need control multiple entries at once. For example, we cannot properly test independently (i.e., in two separate iterations) for `UseTab` and `TabWidth`; we cannot properly find the right value for `UseTab` without the proper `TabWidth`, and similarly, we can't find the right `TabWidth` with a wrong `UseTab` value.

In this case, we allow the following syntax:
```
- UseTab:
    - Never
    - ForIndentation4: {UseTab: ForIndentation, TabWidth: 4}
    - ForIndentation8: {UseTab: ForIndentation, TabWidth: 8}
    - ForIndentation2: {UseTab: ForIndentation, TabWidth: 2}
    - ForContinuationAndIndentation4: {UseTab: ForContinuationAndIndentation, TabWidth: 4}
    - ForContinuationAndIndentation8: {UseTab: ForContinuationAndIndentation, TabWidth: 8}
    - ForContinuationAndIndentation2: {UseTab: ForContinuationAndIndentation, TabWidth: 2}
    - Always4: {UseTab: Always, TabWidth: 4}
    - Always8: {UseTab: Always, TabWidth: 8}
    - Always2: {UseTab: Always, TabWidth: 2}
```

We still use a key and a list of values, but we can explicitly state what those values mean, and what clang-format options to add.

In the above example, the `Never` value of `UseTab` will be translated to `UseTab: Never`, but there is no direct translation for the rest of the values. For example, for the `Always4` option, the script is directed to use the settings defined by `{UseTab: Always, TabWidth: 4}`.


## COVID-19

Although the idea for this script was slightly older, the development of this started in March 2020, in the time of [COVID-19](https://en.wikipedia.org/wiki/Coronavirus_disease_2019). Influenced by the events from Italy, where fatalities skyrocketed, there was no better time to start working on this.

Dear Italians, stay at home, isolated, but don't feel lonely. We have you in our hearts. :heart:

Let this be in the remembrance of tragic events that happened in Italy during this period.
