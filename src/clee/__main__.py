import cmd
import os, sys
try:
    import readline
except:
    readline = None
import re
import argparse
import shlex
import signal
from fuzzywuzzy import process as fuzz
import textwrap

from pyautogui import press

from .cli_util import *

real_print = print

def getYesNo(question):
    ans = None
    while ans not in ["Y", "N"]:
        ans = input(question+" (Y/N) > ").upper()
    return ans == "Y"

def extract_refs(comment):
    objrefs = []
    signrefs = []

    comment = re.sub("[^ :0-9A-Za-z~+@]", " ", comment).split(" ")
    comment = [token for token in comment if token != ""]
    comment = ' '.join(comment)

    for uid in re.findall(r'P[0-9]+[^ ]*', comment):
        query = cursor.execute("SELECT UID FROM Object WHERE UID = ?", (uid,))
        for (row,) in query.fetchall():
            objrefs.append(row)
    for publication in re.findall(r'([A-Za-z]+ [0-9]+[A-Z]?(,? [0-9]+)?)', comment):
        publication = publication[0]
        query = cursor.execute("SELECT DISTINCT UID, Value FROM ObjectAttributeValue WHERE Attribute = 'publication'") #, (publication[0]+'%',))
        rows = [(u, p.upper()) for (u,p) in query.fetchall()]

        match, score = fuzz.extractOne(publication, [re.sub("[,]", "", p) for _, p in rows])
        if score > 95:
            objrefs.append([(u,p) for u, p in rows if re.sub("[,]", "", p) == match][0])

        for u, p in rows:
            if publication in p:
                objrefs.append((u,p))

    for sign in re.findall(r'M[0-9X]{1,3}[-~a-zA-Z0-9+|]*', comment):
        canonical = ''
        sign = sign.upper()
        for Mgroup, rest in re.findall(r'M([0-9X]+)([^M]*)', sign):
            if 'X' in Mgroup:
                number = 'XXX'
            else:
                number = f"{int(Mgroup):03}"
            canonical += "M" + number + rest 
        query = cursor.execute("SELECT SignID FROM Signs WHERE DahlName = ?", (canonical,))
        if rows := query.fetchall():
            for (signid,) in rows:
                signrefs.append((signid, canonical))
        else:
            signrefs.append((None, canonical))

    objrefs_ = []
    signrefs_ = []
    if objrefs:
        # print(f"Found references to {len(objrefs)} objects:")
        for uid in objrefs:
            if len(uid) == 2:
                uid, pub = uid
                item = f"{pub} (= {uid})"
            else:
                item = f"{uid}"
            link = getYesNo(f"Does this comment refer to {item}?")
            if link:
                objrefs_.append(uid)

    if signrefs:
        #print(f"Found references to {len(signrefs)} sign types:")
        for signid, sign in signrefs:
            item = f"{sign}"
            if signid == None:
                print(f"This comment appears to refer to {item}, but no such sign exists.")
                continue
            link = getYesNo(f"Does this comment refer to {item}?")
            if link:
                signrefs_.append(signid)
    return objrefs_, signrefs_

class CLEE(cmd.Cmd):
    intro = "\033[2J\033[H\n" + \
            "░░░░░░░░░░█▀▀░█░░░█▀▀░█▀▀░░░░░░░░░░".center(70) + "\n" + \
            "░░░░░░░░░░█░░░█░░░█▀▀░█▀▀░░░░░░░░░░".center(70) + "\n" + \
            "░░░░░░░░░░▀▀▀░▀▀▀░▀▀▀░▀▀▀░░░░░░░░░░".center(70) + "\n" + \
            "CommandLine Environment for Elamite".center(70) + "\n" + \
            "Type help or ? to list commands.".center(70) + "\n"

    prompt = "\n┏" + "━"*70 + "\n┗ CLEE > "

    selection = set()
    # Number of UIDs to print when showing selected objects.
    selection_limit = 10

    def __init__(self):
        super().__init__()
        self.ignore = False
    
    def completion(self, text, line, options):
        mline = line.partition(' ')[2]
        offs = len(mline) - len(text)
        return [s[offs:] for s in options if s.startswith(mline)]

    def do_atf(self, line):
        """
        Print the raw ATF for a given P-number.

        Usage:
        atf uid

        Examples:
        atf P009309
        """
        try:
            with open(os.path.join(atf_path, f"{line}.atf")) as fp:
                print(fp.read())
        except:
            print(f"Could not find ATF file for {line}")

    def do_grep(self, line):
        """
        Print lines which match a pattern, and highlight that pattern.

        Usage:
        grep pattern
        -- right now, pattern must be a single M-sign. More complex
           patterns will be supported in the future.

        Examples:
        grep M004~b

        grep M157+M288
        """
        if sign := is_sign(line):
            if "+" in sign:
                components = sign.split("+")

                # TODO extract to a method to reduce duplication
                # cf. repeated code in do_describe
                try:
                    (left_id,) = cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (components[0],)).fetchone()
                    (middle_id,) = cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (components[1],)).fetchone()
                    if len(components) == 3:
                        (right_id,) = cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (components[2],)).fetchone()
                except:
                    return
                if len(components) == 3:
                    texts = get_texts_by_cg(left_id, middle_id, right_id)
                else:
                    texts = get_texts_by_cg(left_id, middle_id)
            else:
                try:
                    (sign_id, base_name) = cursor.execute("SELECT SignID, BaseName from Signlist WHERE DahlName = ?", (sign,)).fetchone()
                except:
                    sign_id = None
                if sign_id:
                    texts = get_texts_by_sign(sign_id)
                else:
                    return
            list_idx = 0
            # Monkeypatch print to highlight strings
            # matching the given pattern
            import builtins
            def grep_print(*args, **kwargs):
                real_print(*[re.sub(f'({re.escape(sign)})', r'\033[31;1m\1\033[0m', a) for a in args], **kwargs)
            builtins.print = grep_print
            while 0 <= list_idx < len(texts):
                uid, _ = texts[list_idx]
                self.do_describe(uid)
                choice = None
                while not choice: 
                    choice = input(f"[n]ext text, [p]rev text, [q]uit, or enter a number to jump to the nth text (1-{len(texts)}) > ")
                    if choice == "n":
                        list_idx += 1
                    elif choice == "p":
                        list_idx -= 1
                    elif choice == "q":
                        list_idx = -1
                    else:
                        try:
                            list_idx = int(choice)-1
                        except:
                            choice = None
            builtins.print = real_print

    def do_errors(self, line):
        """
        Print a list of known issues which need to be fixed.
        """
        # List signs which are used in the ATF but do not occur in the Signlist:
        cursor.execute("SELECT GROUP_CONCAT(UID), Value FROM ObjectAttributeValue WHERE Attribute = 'DahlName' AND UID IN (SELECT DISTINCT UID FROM ObjectAttributeValue WHERE Attribute = 'SignID' and Value = -1) GROUP BY Value ORDER BY Value")
        for (tokens, name) in cursor.fetchall():
            if name in ["X", "...", "N00"]:
                continue
            print(f"Sign '{name}' does not exist in the signlist. Used on {tokens.count(',')+1} tokens: {', '.join(tokens.split(',')[:5]) + (', ...' if tokens.count(',') > 4 else '')}")

    def do_rename(self, line):
        """
        Change the SignID associated with a given token.

        Usage:
        rename uid dahlname

        Examples:
        rename P009001:4:sgn:0 M157~a
        -- relabels P009001:4:sgn:0 (the first sign of P009001) as M157~a
        """
        parser = argparse.ArgumentParser(exit_on_error=False)
        parser.error = lambda x: print(x)
        parser.add_argument(
            '_id',
            type=str,
        )
        parser.add_argument(
            '_name',
            type=str,
        ) 
        args = parser.parse_args(shlex.split(line))

        try:
            uid = canonical_uids[args._id.upper()]
        except Exception as e:
            print(f"Unknown UID: {args._id}")
            return

        name = args._name.upper()
        cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (name,))
        if not (rows := cursor.fetchall()):
            allowMissing = getYesNo(f"WARNING: no sign called {name} exists in the Signlist. Do you want to proceed?")
            if allowMissing:
                sign_id = -1
            else:
                print("Aborting")
                return
        elif len(rows) > 1:
            print(f"Found more than one sign matching the name '{name}': SignIDs {rows}")
            print("Aborting")
            return
        else:
            (sign_id,) = rows[0]

        cursor.execute("UPDATE ObjectAttributeValue SET Value = ? WHERE UID = ? AND Attribute = 'DahlName'", (name, uid))
        cursor.execute("UPDATE ObjectAttributeValue SET Value = ? WHERE UID = ? AND Attribute = 'SignID'", (sign_id, uid))
        db.commit()

        print(f"Updated token {uid} with DahlName {name} (SignID {sign_id})")
        
    def do_annotate(self, line):
        """
        Add, remove, or update an object-attribute-value triple.

        Usage:
        annotate (add|update|delete|rename) uid attribute value

        Examples:
        annotate add P008001 provenience "Susa, mod. Shush"
        -- adds a "provenience" attribute to P008001 with the value "Susa, mod. Shush"

        annotate update P008001 provenience Susa
        -- changes the "provenience" attribute of P008001 to just "Susa"

        annotate rename P008001 provenience provenance
        -- renames the "provenience" attribute of P008001 to "provenance"

        annotate delete P008001 provenance Susa
        -- deletes the "provenance" attribute from P008001 where the current value is "Susa"
        -- if P008001 has multiple provenance attributes with different values, only the one
           with value "Susa" will be deleted.
        """
        # annotate UID attribute value
        # prompt if exists
        parser = argparse.ArgumentParser(exit_on_error=False)
        parser.error = lambda x: print(x)
        parser.add_argument(
            '_action',
            type=str,
            choices=["add", "update", "delete", "rename"],
        )
        parser.add_argument(
            '_id',
            type=str,
        )
        parser.add_argument(
            '_attr',
            type=str,
        )
        parser.add_argument(
            '_value',
            nargs='*',
            default=''
        )
        try:
            args = parser.parse_args(shlex.split(line))
            cursor.execute("SELECT * FROM Object WHERE UID = ?", (args._id,))
            if not (rows := cursor.fetchall()):
                raise Exception(f"No such UID: {args._id}")

            # check for existing OAV triple:
            cursor.execute("SELECT * FROM ObjectAttributeValue WHERE UID = ? AND Attribute = ?", (args._id,args._attr))
            current = cursor.fetchall()

            action = args._action
            value = ' '.join(args._value)

            if not current and action == 'rename':
                raise Exception(f"Cannot rename: {args._id} has no property {args._attr}")
            if current and action == 'add':
                uid, attr, val = current[0]
                print(f"{uid} already has value {val} for property {attr}.")
                update = getYesNo("Do you want to overwrite this value?")
                if update:
                    action = 'update'
                else:
                    action = 'none'

            if action == 'add':
                cursor.execute("INSERT INTO ObjectAttributeValue VALUES (?, ?, ?)", (args._id, args._attr, value))
                db.commit()
            elif action == 'update':
                cursor.execute("UPDATE ObjectAttributeValue SET Value = ? WHERE UID = ? AND Attribute = ?", (value, args._id, args._attr))
                db.commit()
            elif action == 'delete':
                cursor.execute("DELETE FROM ObjectAttributeValue WHERE UID = ? AND Attribute = ? AND Value = ?", (args._id, args._attr, value))
                db.commit()
            elif action == 'rename':
                cursor.execute("UPDATE ObjectAttributeValue SET Attribute = ? WHERE UID = ? AND Attribute = ?", (value, args._id, args._attr))
                db.commit()

        except Exception as e:
            print(e)


    def do_desc(self, line):
        """
        Shorthand for the describe command.

        Type "? describe" for documentation.
        """
        self.do_describe(line)

    def do_describe(self, line):
        """
        Prints summary information about a UID or sign.

        Usage:
        describe uid
        describe dahlname
        
        Examples:
        describe P008791
        -- prints information about the tablet P008791, including the full text in transliteration
        -- if there are any comments attached to the tablet, they will be printed, as will comments
           attached to the text's entries, tokens, numerals, and other sub-parts.

        describe P008002:6:sgn:0
        -- prints information about the token P008002:6:sgn:0, including information about its
           component parts (it is a CG) and a transliteration of the entry it occurs in.

        describe M106+M288
        -- prints information about the sign M106+M288, including its frequency and a list of 
           texts where it occurs. Frequency information is computed on-the-fly from the database
           to ensure that it remains up-to-date.
        """
        # Try to parse input as...
        # UID
        if uid := is_uid(line):
            prettyprint(uid)

        # Sign name
        elif sign := is_sign(line):
            line = sign
            show_texts = True

            try:
                (sign_id,base_name) = cursor.execute("SELECT SignID, BaseName from Signlist WHERE DahlName = ?", (sign,)).fetchone()
                if base_name != sign:
                    draw_header("variants")
                    print(f"{sign} (sign id {sign_id}) is a variant of {base_name}\n")
                else:
                     cursor.execute("SELECT SignID, DahlName from Signlist WHERE BaseName = ? AND DahlName != ?", (base_name,sign))
                     if rows := cursor.fetchall():
                        draw_header("variants")
                        print(f"{sign} (sign id {sign_id}) has variants {', '.join([r for _, r in rows])}\n")

                show_comments_by_sign(sign_id, sign)

            except:
                print(f"{sign} looks like a sign name, but it's not in the signlist.\n")
                show_texts = False

            if "+" in sign:
                components = sign.split("+")

                try:
                    (left_id,) = cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (components[0],)).fetchone()
                    draw_header("components")
                    print(f"The component {components[0]} has sign id {left_id}")
                except:
                    print(f"The component {components[0]} is not in the signlist")
                    show_texts = False
                try:
                    (middle_id,) = cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (components[1],)).fetchone()
                    print(f"The component {components[1]} has sign id {middle_id}")
                except:
                    print(f"The component {components[1]} is not in the signlist")
                    show_texts = False
                try:
                    if len(components) == 3:
                        (right_id,) = cursor.execute("SELECT SignID FROM Signlist WHERE DahlName = ?", (components[2],)).fetchone()
                        print(f"The component {components[2]} has sign id {right_id}")
                except:
                    print(f"The component {components[3]} is not in the signlist")
                    show_texts = False
                
                print()
                if show_texts:
                    if len(components) == 3:
                        texts = get_texts_by_cg(left_id, middle_id, right_id)
                    else:
                        texts = get_texts_by_cg(left_id, middle_id)
                else:
                    return

            elif show_texts:
                texts = get_texts_by_sign(sign_id)
            else:
                return

            draw_header("attestations")
            print(f"{sign} is attested {sum([c for _, c in texts])} times in {len(texts)} texts:")
            attestations = ', '.join(
                [f"{text} (x{count})" 
                 for text, count 
                 in sorted(texts, key=lambda x:x[1], reverse=True)])
            for line in textwrap.wrap(attestations, initial_indent='  ', subsequent_indent="  "):
                print(line)
            print()

        else:
            print(f"Unknown identifier: '{line}'")

    #def complete_comment(self, line, text, begidx, endidx):
        #return self.completion(line, text, 
            #[uid for uid in get_object.by_uid.keys()
             #if uid.count(':') <= text.count(":")+1])
    def complete_desc(self, line, text, begidx, endidx):
        return self.completion(line, text, 
            [uid for uid in canonical_uids.values()
             if uid.count(':') <= text.count(":")+1                         # complete up to the next colon
             or (uid.count(":") == 2 and len(text.split(" ")[-1]) == 7)])   # ... or 2 colons if the last word is a complete P-number

    def do_comment(self, line):
        """
        Add a comment and link it to a sign or UID. CLEE will
        try to automatically link any UIDs or sign names mentioned
        in the comment, but at present this doesn't work for digits.

        Usage:
        comment "comment goes here" (-u uid) (-s dahlname)

        Examples:
        comment M176 occurs once as a possible header (P008707), twice as the second sign in a possible 2-sign header (P009059, P008985), and twice as a subscript (P008709, and P008205 as M176~b) 
        -- CLEE will ask to confirm which signs and texts this comment should be linked to:
            Does this comment refer to P008707? (Y/N) > y 
            Does this comment refer to P009059? (Y/N) > y 
            Does this comment refer to P008985? (Y/N) > y 
            Does this comment refer to P008709? (Y/N) > y 
            Does this comment refer to P008205? (Y/N) > y 
            Does this comment refer to M176? (Y/N) > y 
            Does this comment refer to M176~B? (Y/N) > y 

        comment "Transliteration mistake: expect a 2.5:1 ratio of M56:M288, which means the final sign on the obverse should be N39B. Visual inspection is also consistent with N39B." -u P008791:7:num -s N39B
        -- -u links the comment to a UID which was not mentioned in the text
        -- since CLEE cannot automatically detect N-signs at the moment, -s is used to link the comment to N39B
        -- CLEE will recognize shorthands like M56 as referring to M056
        """
        parser = argparse.ArgumentParser(exit_on_error=False)
        parser.add_argument(
            'comment',
            type=str,
            nargs='*',
        )
        parser.add_argument(
            '-u', '--uid',
            nargs='*',
            action='append',
            default=[[]],
            type=lambda x:(str(x).capitalize()),
        )
        parser.add_argument(
            '-s', '--sign',
            nargs='*',
            action='append',
            default=[[]],
            type=lambda x:(str(x).upper()),
        )
        try:
            args = parser.parse_args(shlex.split(line))

            if isinstance(args.comment, list):
                comment = ' '.join(args.comment)
            else:
                comment = args.comment

            if comment == '':
                raise Exception("Empty comment?")

            extracted_uid, extracted_sign = extract_refs(comment)

            # verify object references
            for uid in args.uid[-1]:
                uid = uid.upper()
                if uid not in canonical_uids:
                    raise ValueError(f"Object not found: {uid}")
                extracted_uid.append(canonical_uids[uid])
            # verify type references
            for sign in args.sign[-1]:
                sign = sign.upper()
                query = cursor.execute("SELECT SignID FROM Signs WHERE DahlName = ?", (sign,))
                if rows := query.fetchall():
                    for (signid,) in rows:
                        extracted_sign.append(signid)
                else:
                    raise ValueError(f"Sign not found: {sign}.")

            add = True
            if len(extracted_uid) == len(extracted_sign) == 0:
                add = getYesNo("This comment does not refer to any objects or signs. Add it anyways?")
            print("Inserting comment...")
            cursor.execute("INSERT INTO Comment(Comment) VALUES (?)", (comment,))
            commentid = cursor.lastrowid
            print(f"Inserted comment with CommentID = {commentid}")
            for uid in extracted_uid:
                cursor.execute("INSERT INTO ReferencesObject(CommentID, UID) VALUES (?, ?)", (commentid, uid))
                print(f"Linked comment {commentid} to object {uid}")
            for signid in extracted_sign:
                cursor.execute("INSERT INTO ReferencesSign(CommentID, SignID) VALUES (?, ?)", (commentid, signid))
                print(f"Linked comment {commentid} to sign {signid}")
            db.commit()
        except Exception as e:
            print(e)
            print("Errors occured, comment not recorded.")
        pass

    def preloop(self):
        if readline and os.path.exists(histfile):
            readline.read_history_file(histfile)
    def precmd(self, line):
        if self.ignore:
            self.ignore = False
            return ' '

        if isinstance(line, tuple):
            return line

        if readline:
            readline.set_history_length(histfile_size)
            readline.write_history_file(histfile)

        line = line.strip()
        line = re.sub("", "", line)
        return line

    def emptyline(self):
        pass
    def default(self, line):
        pass

    def do_exit(self, line):
        """
        Close the application. CLEE will miss you :(
        """
        return self.close()

    def do_EOF(self, line):
        return self.close()

    def close(self):
        print("Goodbye")
        return True

    def ignore_next(self):
        self.ignore = True

def ctrl_c(clee):
    def handler(signal, frame):
        # print a ^C
        readline.insert_text("^C")
        readline.redisplay()
        # tell CLEE to skip the next command
        clee.ignore_next()
        # simulate user pressing Enter, to
        # clear the input buffer and print a
        # clean prompt
        press("Enter")
    return handler

if __name__ == "__main__":
    clee = CLEE()
    
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler=ctrl_c(clee))
    
    clee.cmdloop()
