from collections import defaultdict
import re
import sqlite3
import time
import os
import textwrap

clee_dir = os.path.join(os.path.expanduser('~'), '.clee')
if not os.path.exists(clee_dir):
    os.makedirs(clee_dir)

histfile = os.path.join(clee_dir, 'history')
histfile_size = 1000

logfile = os.path.join(clee_dir, 'sql.log')

db_path = os.path.join(clee_dir, 'grist.db')

atf_path = os.path.join(clee_dir, 'atf')

def log_sql(query):
    with open(histfile, 'r') as fp:
        command = fp.read().splitlines()[-1]
    with open(logfile, 'a+') as fp:
        fp.write(f"{time.ctime()} │ {command} │ {query}\n")

db = sqlite3.connect(db_path)
db.set_trace_callback(log_sql)
cursor = db.cursor()

cursor.execute("SELECT DISTINCT UID FROM Object")
canonical_uids = cursor.fetchall()
# Uppercase the UIDs for ease of comparing to user input,
# but maintain the original casing for DB access:
canonical_uids = {uid.upper(): uid for (uid,) in canonical_uids}

hide_uid_col = True

def is_uid(string):
    """
    Returns the canonical form of a UID, or False.

    :param string: A string which might be a UID.
    :returns: The canonical form of the input string, if it is a valid UID, else False.
    """
    try:
        return canonical_uids[string.upper()]
    except:
        return False

def show_comments_by_uid(uid):
    show_comments_(
        "ReferencesObject", 
        "UID", 
        ":".join(uid.split(":")[:2]), # fetch all comments from the same line/tablet to give better context
        uid, 
        approx=True
    )

def show_comments_by_sign(sign_id, dahlname):
    show_comments_("ReferencesSign", "SignID", sign_id, dahlname)

def mentioned_entities(comment_id):
    """
    Return the UID or SignID of any entities associated with this comment.

    :param comment_id: A valid CommentID from the Comment table.
    :returns: A tuple `(uids, signs)` where `uids` is a list of UIDs associated with the given comment, and `signs` is a list of sign names associated with that comment.
    """
    cursor.execute("SELECT UID from ReferencesObject WHERE CommentID = ?", (comment_id,))
    uids = cursor.fetchall()
    
    cursor.execute("SELECT DahlName from (ReferencesSign NATURAL JOIN Signs) WHERE CommentID = ?", (comment_id,))
    signs = cursor.fetchall()

    return uids, signs

def draw_header(title):
    print(("╔" + "═"*20 + "╗").center(70))
    print(("║" + f"{title.upper():^20}" + "║").center(70))
    print(("╚" + "═"*20 + "╝").center(70))

def show_comments_(table, column, id_, name, approx=False):
    if approx:
        cursor.execute(f"SELECT CommentID, Comment from Comment NATURAL JOIN {table} WHERE {column} LIKE ?||'%'", (id_,))
    else:
        cursor.execute(f"SELECT CommentID, Comment from Comment NATURAL JOIN {table} WHERE {column} = ?", (id_,))
    comments = cursor.fetchall()

    if len(comments) == 0:
        #print(f"There are no comments which mention {name}.")
        return

    draw_header("comments")
    #print(f"{len(comments)} comments mention {name}:")
    for comment_id, comment in comments:
        for line in textwrap.wrap(comment, initial_indent="• ", subsequent_indent='  '):
            print(line)
        uids, signs = mentioned_entities(comment_id)
        for (uid,) in uids:
            if uid != name:
                print(f"  ↳ see also {uid}")
        for (sign,) in signs:
            if sign != name:
                print(f"  ↳ see also {sign}")
        print()

def get_type(uid):
    if ":" not in uid:
        return "tablet"
    elif uid.endswith(":1sg"):
        return "first segment"
    elif uid.endswith(":ent"):
        return "entry"
    elif uid.endswith(":txt"):
        return "text span"
    elif uid.endswith(":num"):
        return "numeral"
    elif uid.endswith(":n"):
        raise Exception(f"n-sign objects have been deprecated: UID {uid} should not exist.")
    elif ":sgn:" in uid:
        # TODO
        # digit
        # cg
        # msign == cg component
        return "sign"
    else:
        return f"UNKNOWN ({uid})"

"""
def get_children(uid):
    cursor.execute("" "
      WITH tmp(parent, ignore, child) AS 
        (SELECT * FROM ObjectAttributeValue 
         WHERE Attribute = 'child' 
         AND UID = ? 
           UNION ALL SELECT ObjectAttributeValue.UID, 'child', ObjectAttributeValue.Value 
           FROM (ObjectAttributeValue JOIN tmp ON ObjectAttributeValue.UID = tmp.child) 
           WHERE ObjectAttributeValue.Attribute = 'child'
      ) SELECT DISTINCT parent, child FROM tmp" "", (uid,))
    return cursor.fetchall()

def split_uid(uid):
    uid = uid.split(":")
    return [int(uid[0][1:])] + [int(item) for item in uid if item.isnumeric()]

def get_signs(uid):
    children = [(parent_id, child_id) 
                for parent_id, child_id in get_children(uid)
                if ":sgn:" in child_id]
    lines = []
    for parent, child in sorted(children, key=lambda pair:split_uid(pair[1])):
        if lines == [] or lines[-1][0] != parent:
            lines.append([parent, split_uid(parent)[1], []])
        lines[-1][-1].append(child)
    return lines


def format_token(uid):
    sign_id  = get_attr(uid, 'SignID')
    sign_name = get_sign_by_id(sign_id)
    if not sign_name:
        try:
            sign_name = get_attr(uid, 'DahlName')
        except:
            sign_name = "UNK"
        if sign_name not in ["X", "...", "N00"]:
            sign_name += "(!)"

    try:
        quantity = get_attr(uid, 'quantity')
        return f"{quantity}({sign_name})"
    except:
        return f"{sign_name}"
    """

def get_sign_info(sign_id):
    cursor.execute("SELECT DahlName FROM Signlist WHERE SignID = ?", (sign_id,))
    if not (rows := cursor.fetchall()):
        return (None,)
    else:
        return rows[0]

def get_parents(uid):
    cursor.execute("SELECT Value, GROUP_CONCAT(UID) FROM ObjectAttributeValue WHERE Attribute = 'child' AND Value LIKE ?||'%' GROUP BY Value", (uid,))
    mapping = dict()
    for child, ancestors in cursor.fetchall():
        mapping[child] = ancestors.split(",")
    return mapping

def get_ancestors(uid):
    parents    = get_parents(uid)
    ancestors = parents; ancestors_ = parents
    while True:
        for k in ancestors:
            new = ancestors[k] + sum([ancestors[p] for p in ancestors[k] if p in ancestors],[])
            ancestors_[k] = sorted(list(set(new)))
        if all(ancestors[k] == ancestors_[k] for k in ancestors):
            break
        ancestors_ = ancestors
    return ancestors

def prettyprint_tablet(uid, head=None):
    cursor.execute("""
    WITH sgn AS 
    ( -- get :sgn: objects with the given UID as prefix:
      SELECT UID FROM Object WHERE UID LIKE ?||'%sgn%'
    ), dname AS (
      SELECT * FROM sgn NATURAL JOIN ObjectAttributeValue WHERE Attribute = 'DahlName'
    ), sid AS (
      SELECT * FROM sgn NATURAL JOIN ObjectAttributeValue WHERE Attribute = 'SignID'
    ), qty as (
      SELECT * FROM sgn NATURAL JOIN ObjectAttributeValue WHERE Attribute = 'quantity'
    ) SELECT sgn.UID, dname.Value, sid.Value, Signs.DahlName, qty.Value 
    FROM 
    (
      (sgn LEFT JOIN dname ON sgn.UID = dname.UID) 
      LEFT JOIN sid ON dname.UID = sid.UID 
      LEFT JOIN Signs ON sid.Value = Signs.SignID
    ) LEFT JOIN qty on qty.UID = sgn.UID 
    ORDER BY CAST(SUBSTR(SUBSTR(sgn.UID, 9), 0, INSTR(SUBSTR(sgn.UID,9),':')) AS INTEGER), 
                  SUBSTR(sgn.UID, INSTR(sgn.UID,'sgn:')+4)
    """,(uid,))
    tokens = {
        UID: (lambda name:f"{quantity}({name})" if quantity else name)(
                DahlName if DahlName 
                else f"{fallback}{'(!)' if fallback not in ['X', '...', 'N00'] else ''}") 
        for UID, fallback, _, DahlName, quantity in cursor.fetchall()
    }

    ancestors = get_ancestors(uid)
    all_uids = set(sum(ancestors.values(), []) + list(ancestors.keys()))
    descendents = {anc:[desc for desc in all_uids if desc in ancestors and anc in ancestors[desc]] for anc in all_uids}

    cursor.execute("""
    SELECT * 
    FROM ObjectAttributeValue 
    WHERE Attribute LIKE 'val_%' AND UID IN ({})
    """.format(', '.join(f"'{u}'" for u in all_uids if ':num' in u)))
    values = defaultdict(dict)
    for entry, system, value in cursor.fetchall():
        values[entry][system[4:]] = value

    cursor.execute("SELECT DISTINCT UID FROM ObjectAttributeValue WHERE UID LIKE ?||'%' AND Attribute = 'span_type' AND Value = 'HEADER'",(uid,))
    headers = set(h[7:] for (h,) in cursor.fetchall())
    
    n_lines = max(int(uid_.split(":")[1]) for uid_ in ancestors.keys() if ":" in uid_)
    lines = []
    for n in range(n_lines+1):
        toks = sorted([uid_ for uid_ in tokens if int(uid_.split(":")[1]) == n])
        if len(toks) == 0:
            continue
        lines.append([[],[],[],[]])
        spans = [uid_ for uid_ in all_uids if any(uid_ in ancestors[t] for t in toks)]
        num_id = None
        for type_ in [":1sg", ":ent", ":txt", ":num"]:
            for span in spans:
                if type_ in span:
                    lines[-1][0].append(f"{span[7:]:9}")
                    if type_ == ":num":
                        num_id = span
                    break
            else:
                lines[-1][0].append(f"{'':9}")
        # print text
        for i, tok_id in enumerate(toks):
            if any(":num" in anc for anc in ancestors[tok_id]):
                continue
            tok = tokens[tok_id]
            if tok != "None(!)":
                end=' '
                if len(tok_id.split(":")) > 4:
                    if i+1 < len(toks) and len(toks[i+1].split(":")) > 4:
                        end='+'
                lines[-1][1].append(f"{tok+end}")
        # print numeral
        for i, tok_id in enumerate(toks):
            if any(":txt" in anc for anc in ancestors[tok_id]):
                continue
            tok = tokens[tok_id]
            if tok != "None(!)":
                end=' '
                if len(tok_id.split(":")) > 4:
                    if i+1 < len(toks) and len(toks[i+1].split(":")) > 4:
                        end='+'
                lines[-1][2].append(f"{tok+end}")
        # print numeral value(s)
        if num_id:
            n_vals = len(values[num_id])
            for value_line, (system, value) in enumerate(sorted(values[num_id].items())):
                value = float(value)
                value = re.sub('\.00', '   ', '{:>6.2f}'.format(round(value,2)))
                if value_line > 0:
                    lines.append([[],[],[],[]])
                #lines[-1][3].append(f"{r'─' if value_line == 0 and n_vals == 1 else '┬' if value_line == 0 and n_vals > 1 else '├' if value_line < n_vals-1 else '└'} {value} xN01 ({system.replace(',','')}) ")
                lines[-1][3].append(f"{'=' if value_line == 0 else ' '} {value} xN01 ({system.replace(',','')}){',' if value_line < n_vals-1 else ' '}")
    #print(any(h.strip() in headers for h in lines[0][0]))
    if lines != []:
        lines = [[[]]+l[1:]+l[:1] for l in lines]
        # TODO if HMM header, also label the later rows
        lines = [l[:1]+['H ' if any(h.strip() in headers for h in l[-1]) else ' ']+l[1:] for l in lines]
        lines = [[''.join(col) for col in l] for l in lines]
        lines = [['', '  ', 'TEXT ', 'NUMERAL ', 'VALUE(S)', F'{"SEGMENT":9}{"ENTRY":9}{"TEXT":9}{"NUMERAL":9}']] + lines
        if head:
            lines = lines[:head+1]
        col_widths = [max(len(l[i]) for l in lines) for i in range(len(lines[0]))]
        if hide_uid_col or sum(col_widths[:-1]) > 70:
            lines = [l[:-1]+[''.join(re.findall(':[0-9]+', ''.join(l[-1]))[-1:])] for l in lines]
            col_widths[-1] = 5
            lines[0][-1] = 'LINE '
        for line_no, l in enumerate(lines):
            if line_no == 0:
                for i in range(len(lines[0])):
                    if i == 0:
                        print("\033[1m┌", end='')
                    else:
                        print("─"*(col_widths[i]+1), end='┬' if i < len(lines[0])-1 else "┐\n")
            for i in range(len(lines[0])):
                # Right-align the text column, so
                # that counted objects are lined up
                if i == 1:
                    fmt = "{:>{w}}"
                else:
                    fmt = "{:<{w}}"
                print(fmt.format(l[i],w=col_widths[i]), end='│')
                if i < len(l)-1:
                    print(' ', end='')
            if line_no == 0:
                for i in range(len(lines[0])):
                    if i == 0:
                        print("\n├", end='')
                    else:
                        print("─"*(col_widths[i]+1), end='┼' if i < len(lines[0])-1 else "┤\033[0m")
            if line_no == len(lines)-1:
                for i in range(len(lines[0])):
                    if i == 0:
                        print("\n└", end='')
                    else:
                        print("─"*(col_widths[i]+1), end='┴' if i < len(lines[0])-1 else "┘")
            #if line_no == 0 or line_no == len(lines)-1:
                #print("\033[0m",end='')
            print()

def get_attrs(uid):
    cursor.execute("SELECT Attribute, GROUP_CONCAT(Value) from ObjectAttributeValue WHERE UID = ? GROUP BY Attribute", (uid,))
    av_pairs = cursor.fetchall()
    av_dict = defaultdict(set)
    for attr, val in av_pairs:
        av_dict[attr].add(val)
    return av_dict

def prettyprint(uid):
    type_ = get_type(uid)
    av_dict = get_attrs(uid)

    draw_header(uid)
    if (type_ := get_type(uid)) == "tablet":
        if 'publication' in av_dict:
            (publication,) = av_dict['publication']
            print(f"{uid} is the UID for {publication}\n")
        prettyprint_tablet(uid)

    elif type_ in ["entry", "text span", "numeral"]:
        #print(f"{uid} is the UID for {'an' if type_[0] in 'aeiou' else 'a'} {type_}\n")
        prettyprint_tablet(uid[:-4])

    elif type_ == "sign":
        (sign_id,) = av_dict.get('SignID', (None,))
        if sign_id:
            (dahlname,) = get_sign_info(sign_id)
            if not dahlname:
                (dahlname,) = av_dict.get('DahlName', (None,))
                print(f"{uid} is an instance of {dahlname}, which does not exist in the signlist.\n")
            else:
                print(f"{uid} is an instance of {dahlname} (sign id {sign_id})\n")
        else:
            cursor.execute("SELECT UID FROM Object WHERE UID LIKE ?||':%'", (uid,))
            parts = cursor.fetchall()
            print(f"{uid} is a complex grapheme with parts ", end='')
            for idx, (part,) in enumerate(parts):
                attrs = get_attrs(part)
                (sign_id,) = attrs.get('SignID', (None,))
                (dahlname,) = get_sign_info(sign_id)
                if not dahlname:
                    (dahlname,) = attrs.get('DahlName', (None,))
                print(f"{dahlname} (sign id {sign_id})", end='')
                if idx != len(parts)-1:
                    print(" and ", end='')
                else:
                    print()
            print()
        
        prettyprint_tablet(':'.join(uid.split(":")[:2]))
    elif type_ == "first segment":
        #print(f"{uid} is the UID for {'an' if type_[0] in 'aeiou' else 'a'} {type_}\n")
        prettyprint_tablet(uid[:7],head=2)

    print()
    show_comments_by_uid(uid)

    ignore_attrs = [
        "child", 
        "digit", 
        "class", 
        "injected_span", 
        "language", 
        "publication", 
        "followed_by", 
        "preceded_by", 
        "sign",
        "component",
        #"span_type",
        "content",
        "numeral",
    ]
    header = False
    for k, v in av_dict.items():
        if k not in ignore_attrs:
            if not header:
                draw_header("attributes")
            print(f"{k}: {', '.join(v)}")
            header = True

def get_texts_by_cg(left_id, middle_id, right_id=None):
    if right_id:
        cursor.execute("""
        WITH Tokens AS (
            SELECT DISTINCT SUBSTR(UID, 1, LENGTH(UID)-2) AS Parent 
            FROM ObjectAttributeValue 
            -- select matching inner part
            WHERE Attribute = 'SignID' AND Value = ? AND UID LIKE '%:sgn:%:1' AND Parent IN (
                SELECT DISTINCT SUBSTR(UID, 1, LENGTH(UID)-2) 
                FROM ObjectAttributeValue 
                -- select matching outer part
                WHERE Attribute = 'SignID' AND Value = ? AND UID LIKE '%:sgn:%:0'
            ) AND Parent IN (
                SELECT DISTINCT SUBSTR(UID, 1, LENGTH(UID)-2) 
                FROM ObjectAttributeValue 
                -- select matching outer part
                WHERE Attribute = 'SignID' AND Value = ? AND UID LIKE '%:sgn:%:2'
            )
        ) SELECT SUBSTR(Parent, 1, 7), COUNT(SUBSTR(Parent, 1, 7))
        FROM Tokens GROUP BY SUBSTR(Parent, 1, 7)""", (middle_id, left_id, right_id))
    else:
        cursor.execute("""
        WITH Tokens AS (
            SELECT DISTINCT SUBSTR(UID, 1, LENGTH(UID)-2) AS Parent 
            FROM ObjectAttributeValue 
            -- select matching inner part
            WHERE Attribute = 'SignID' AND Value = ? AND UID LIKE '%:sgn:%:1' AND Parent IN (
                SELECT DISTINCT SUBSTR(UID, 1, LENGTH(UID)-2) 
                FROM ObjectAttributeValue 
                -- select matching outer part
                WHERE Attribute = 'SignID' AND Value = ? AND UID LIKE '%:sgn:%:0'
            ) AND Parent NOT IN (
                -- remove three-part CGs
                SELECT DISTINCT SUBSTR(UID, 1, LENGTH(UID)-2) 
                FROM Object 
                WHERE UID LIKE '%:sgn:%:2'
            )
        ) SELECT SUBSTR(Parent, 1, 7), COUNT(SUBSTR(Parent, 1, 7))
        FROM Tokens GROUP BY SUBSTR(Parent, 1, 7)""", (middle_id, left_id))
    return cursor.fetchall()

def get_texts_by_sign(sign_id):
    cursor.execute("""
    WITH instances AS (
        SELECT SUBSTR(UID, 1, 7) AS UID 
        FROM ObjectAttributeValue 
        WHERE Attribute = 'SignID'
        AND Value = ?
    ) SELECT UID, COUNT(UID) FROM instances GROUP BY UID;""", (sign_id,))
    return cursor.fetchall()

def is_sign(line):
    if matches := re.match("^\|?((X|M[0-9]+|([0-9]+\()?N[0-9]+[A-Z]*[^)]*\)?)(~[0-9A-Z]+|@[A-Z])?\+?)+\|?$", line.upper()):
        line = line.upper().replace("|", "")
        if "+" not in line and "(" in line:
            line = re.sub(".*\((N[0-9]+[A-Z]*[^)]*)\).*", "\\1", line)
        return line
    return False
