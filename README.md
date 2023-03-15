# Installation

Clone this directory and install with `pip`:
```bash
$ git clone https://github.com/MrLogarithm/clee.git
$ cd clee
$ pip install -e .
```

After installation, you must also extract the backend database and other necessary files to your home directory:
```bash
$ mkdir ~/.clee
$ tar xf data/data.tar --directory ~/.clee
```

When this is done, you may run CLEE:
```bash
$ python -m clee
```

# Usage

Type `?` to see a list of commands, or `? <command-name>` to see the documentation for a particular command.

## atf
Prints the original ATF for a tablet, without any special formatting or additional information.

**Examples**
```
atf P008001
```

## annotate
Add, remove, or update an object-attribute-value triple.

**Usage:**
```
annotate (add|update|delete|rename) uid attribute value
```

**Examples:**
```
annotate add P008001 provenience "Susa, mod. Shush"
```
- adds a "provenience" attribute to P008001 with the value "Susa, mod. Shush"

```
annotate update P008001 provenience Susa
```
- Changes the "provenience" attribute of P008001 to just "Susa"

```
annotate rename P008001 provenience provenance
```
- Renames the "provenience" attribute of P008001 to "provenance"

```
annotate delete P008001 provenance Susa
```
- Deletes the "provenance" attribute from P008001 where the current value is "Susa"
- If P008001 has multiple "provenance" attributes with different values, only the one with value "Susa" will be deleted.

## comment
Add a comment and link it to a sign or UID. CLEE will try to automatically link any UIDs or sign names mentioned in the comment, but at present this doesn't work for digits.

**Usage:**
```
comment "comment goes here" (-u uid) (-s dahlname)
```

**Examples:**
```
comment M176 occurs once as a possible header (P008707), twice as the second sign in a possible 2-sign header (P009059, P008985), and twice as a subscript (P008709, and P008205 as M176~b) 
```
- CLEE will ask to confirm which signs and texts this comment should be linked to:
```
Does this comment refer to P008707? (Y/N) > y 
Does this comment refer to P009059? (Y/N) > y 
Does this comment refer to P008985? (Y/N) > y 
Does this comment refer to P008709? (Y/N) > y 
Does this comment refer to P008205? (Y/N) > y 
Does this comment refer to M176? (Y/N) > y 
Does this comment refer to M176~B? (Y/N) > y 
```

```
comment "Transliteration mistake: expect a 2.5:1 ratio of M56:M288, which means the final sign on the obverse should be N39B. Visual inspection is also consistent with N39B." -u P008791:7:num -s N39B
```
- `-u P008791:7:num` links the comment to a numeral object which was not mentioned in the text (and thus cannot be auto-detected)
- CLEE cannot automatically detect N-signs at the moment, so `-s N39B` is used to link the comment to N39B
- CLEE can recognize shorthands like M56 in place of M056

## desc
Shorthand for `describe`

## describe
Prints summary information about a UID or sign.

**Usage:**
```
describe uid
describe dahlname
```
        
**Examples:**
```
describe P008791
```
- Prints the full text of P008791 in tabular format, with extra information such as line numbers and converted numeral values.
- If there are any comments attached to the tablet, they will be printed, as will comments attached to the tablet's entries, tokens, numerals, and other sub-parts.

```
describe P008002:6:sgn:0
```
- Prints information about the token P008002:6:sgn:0 (the 0th (`:0`) sign (`sgn`) on line 6 (`:6`) of the ATF for P008002), including information about its component parts (it is a CG) and a transliteration of the entry it occurs in.

```
describe M106+M288
```
- Prints information about the sign M106+M288, including its frequency and a list of texts where it occurs. Frequency information is computed on-the-fly from the database to ensure that it remains up-to-date.

## grep
Prints all tablets which contain a given sign, and highlights that sign for emphasis.

**Usage:**
```
grep pattern
```
- At present, pattern must be a single sign. More complex patterns will be supported in the future.

**Examples:**
```
grep M004~b
grep M157+M288
```

## rename
Change the SignID associated with a given token.

**Usage:**
```
rename uid dahlname
```

**Examples:**
```
rename P009001:4:sgn:0 M157~a
```
- Relabels P009001:4:sgn:0 as M157~a. Only affects the labeling of the sign in CLEE's database: the ATF file will not be modified.

## errors
Prints a list of known issues with the corpus.

At present, CLEE is only tracking one kind of error, namely M-numbers which occur in the ATF but do not exist in the signlist (and thus cannot be given as arguments to `describe`, or detected in comments, etc).

## exit
Close the program.
