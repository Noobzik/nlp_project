import shutil
import tarfile
import urllib.request as libreq
import os, sys
import subprocess
from io import StringIO
import csv
import regex as re
from urllib.parse import urlparse
from transformers import TFAutoModelForSeq2SeqLM, AutoTokenizer


def do_preprocessing(file):
    bashcommand = "pandoc test/" + file + " +RTS -M6000m -RTS --verbose --toc --trace --mathjax -f latex -t plain --template=template.plain --wrap=none -o test/" + file[
                                                                                                                                                                    :-4] + ".txt"
    # Ajouter les balises --verbose et --trace pour avoir un output console
    process = subprocess.Popen(bashcommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    print(error)
    if error is None:
        print("pas d erreurs")
    return "test/" + file[:-4] + ".txt"


def process_url(pdf_url):
    url = urlparse(pdf_url)
    path = url.path
    elements = path.split("/")
    dl_url = "/".join([url.scheme + '://www.' + url.netloc, 'e-print', elements[-1][:-4]])
    return (dl_url)


def create_balise(file):
    pass


# file_name, n: nb xmath, m: nb xcite
def my_function(file_name, n, m):
    with open(file_name, encoding='utf8') as f:
        lines = f.read()
    lines_xmath = re.sub("\$(.*?)\$", '@xmath', lines)
    lines_xmath = re.sub(r"(\\begin\{equation\})(.|\n)*?(\\end\{equation\})", '@xmath', lines_xmath)
    splited_lines_xmath = re.split('(@xmath)', lines_xmath)

    cpt = n
    for i in range(len(splited_lines_xmath)):
        if splited_lines_xmath[i] == '@xmath':
            splited_lines_xmath[i] = splited_lines_xmath[i] + str(cpt)
            cpt += 1

    text_modified = "".join(str(x) for x in splited_lines_xmath)

    test = re.compile('\$(.*?)\$')
    mapping = test.findall(lines)
    for i in range(len(mapping)):
        mapping[i] = '@xmath' + str(i + n) + ';' + '$' + mapping[i] + '$'

    test2 = re.compile(r"((\\begin\{equation\})(.|\n)*?(\\end\{equation\}))")
    mapping2 = test2.findall(lines)

    for i in range(len(mapping2)):
        mapping.append('@xmath' + str(i + n + len(mapping)) + ';' + mapping2[i][0])

    lines_xcite = re.sub(r"(\\cite{.*})", '@xcite', lines)
    splited_lines_xcite = re.split('(@xcite)', lines_xcite)
    cpt = m
    for i in range(len(splited_lines_xcite)):
        if splited_lines_xcite[i] == '@xmath':
            splited_lines_xcite[i] = splited_lines_xcite[i] + str(cpt)
            cpt += 1

    text_modified = "".join(str(x) for x in splited_lines_xcite)

    test = re.compile('(\\cite{.*})')
    mapping_cite = test.findall(lines)

    for i in range(len(mapping_cite)):
        mapping_cite[i] = '@xcite' + str(i + n) + ';' + mapping_cite[i]

    f = open("conversion_xcite.txt", "a")
    for i in mapping_cite:
        f.write(i + '\n')
    f.close()

    f = open("conversion_xmath.txt", "a")
    for i in mapping:
        f.write(i + '\n')
    f.close()

    f = open("toto", "w")
    f.write(text_modified)
    f.close()

    nb_xmath = n
    nb_citation = m
    return file_name, nb_xmath, nb_citation


def inference(text, length):
    model = TFAutoModelForSeq2SeqLM.from_pretrained("../checkpoint-110000/", from_pt=True)
    tokenizer = AutoTokenizer.from_pretrained("t5-base")

    # T5 uses a max_length of 512 so we cut the article to 512 tokens.
    inputs = tokenizer("summarize: " + text, return_tensors="tf", max_length=512)
    outputs = model.generate(
        inputs["input_ids"], max_length=length + 10, min_length=length, length_penalty=2.0, num_beams=4,
        early_stopping=True
    )

    print(tokenizer.decode(outputs[0]))
    return tokenizer.decode(outputs[0])


def main(argv):
    try:
        shutil.rmtree('./test', ignore_errors=True)
        os.makedirs("./test")
        pdf_url = argv[0]
        doc = process_url(pdf_url)
        # with libreq.urlopen('https://arxiv.org/e-print/2112.04484') as url:
        with libreq.urlopen(doc) as url:
            r = url.read()
        # print(r)
        with open("test/test.tar", "wb") as f:
            f.write(r)
        tar = tarfile.open("test/test.tar")
        tar.extractall("test/")
        tar.close()
        abstract = ""
        text = ""
        tex_files = []
        for file in os.listdir("test"):
            if file.endswith(".tex"):
                tex_files.append(file)

        print(tex_files)
        for file in tex_files:
            create_balise(file)

        list_txt = []

        n, m = 0, 0
        for file in tex_files:
            f, n, m = my_function('test/' + file, n, m)

        for file in tex_files:
            list_txt.append(do_preprocessing(file))

        for file in list_txt:
            with open(file, 'r') as f:
                lines = f.readlines()
            body_flag = False
            for line in lines:
                if not len(line.strip()):
                    continue
                if line.startswith('BODY'):
                    body_flag = True
                    continue
                if body_flag:
                    text += line
                elif line.startswith('ABSTRACT'):
                    continue
                else:
                    abstract += line
        print("body :", text)
        print("abstract : ", abstract)
        text = text.replace("\"", "'")
        abstract = abstract.replace("\"", "'")
        with open("output.txt", 'w+') as f:
            f.write("abstract, text\n")
            f.write('"' + abstract + '","' + text + '"')

        return inference(text, 200)
    except:
        return "could not process pdf"


if __name__ == '__main__':
    main(sys.argv[1:])
