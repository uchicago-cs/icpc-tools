import random
import string
import sys

if len(sys.argv) != 3:
    print "Usage: python gen_files.py <num files> <file size>"
    exit(1)

nfiles = int(sys.argv[1])
fsize = int(sys.argv[2])

if nfiles > len(string.ascii_uppercase):
    print "Can't generate more than %i problems" % len(string.ascii_uppercase)
    exit(1)

filenames = [ string.ascii_uppercase[i] for i in range(nfiles) ]

for filename in filenames:
    inf = open(filename + ".in", "w")
    outf = open(filename + ".out", "w")

    size = 0
    nlines = 0
    while size < fsize:
        linesize = random.randint(60, 250)
        line = "X" * linesize
        inf.write(line + "\n")
        size += linesize + 1
        nlines += 1

    outf.write(`nlines` + "\n")
    
