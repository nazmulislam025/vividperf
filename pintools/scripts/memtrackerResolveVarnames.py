#!/usr/bin/python 

from os import system
import os.path
import re
import sys
from sys import stdin
import argparse
import ctypes
import commands
import multiprocessing
from multiprocessing import Process

# This dictionary contains all
# memory allocations that we encounter

memAllocations = {}
processes = []

def i2u(i):
    return ctypes.c_uint32(i).value

def notValidHex(num):
    
    try:
        int(num, 16)
        return False;
    except:
        return True;

class MemoryRange:

    def __init__(self, base, size):
        self.strBase = base;
        self.strSize = size;
        self.base = i2u(int(base, 16));
        self.size = i2u(int(size));


    # We consider two memory ranges equal if one
    # contains the other
    #
    def __eq__(self, other):

        if(self.base <= other.base and
           (self.base + self.size) >= other.base):
            return True;
        if(self.base >= other.base and
           self.base <= (other.base + other.size)):
            return True;
        return False;

    def __hash__(self):
        return self.base;

    def __str__(self):
        return ("["+ self.strBase + ", " + self.strSize + "]");

class AllocRecord:

    def __init__(self, threadID, addr, funcName, size, numItems, 
                 sourceLoc, varName, varType):
        self.threadID = threadID;
        self.addr = addr;
        self.funcName = funcName;
        self.size = size;
        self.numItems = numItems;
        self.sourceLoc = sourceLoc;
        self.varName = varName;
        self.varType = varType;

    def __str__(self):
        return ("alloc: " + self.threadID + " " + self.addr + " " 
                + self.funcName + " " + self.size + " " 
                + self.numItems + " " + self.sourceLoc + " " 
                + self.varName + " " + self.varType);


class AccessRecord:

    def __init__(self, accessType, threadID, addr, size, funcName,  
                 varName, varType, allocLoc):

        self.accessType = accessType;
        self.threadID = threadID;
        self.addr = addr;
        self.size = size;
        self.funcName = funcName;
        self.varName = varName;
        self.varType = varType;
        self.allocLoc = allocLoc;


    def __str__(self):
        return (self.accessType + " "  + self.threadID + " " + self.addr + " " 
                + self.size + " " + self.funcName + " "
                + self.varName + " " + self.varType + " "
                + self.allocLoc);


class FuncRecord:

    def __init__(self, eventType, threadID, funcName):
        self.eventType = eventType;
        self.threadID = threadID;
        self.funcName = funcName;

    def __str__(self):
        return (self.eventType + " " + self.threadID + " " +
                self.funcName);

def findOverlappingAlloc(memAllocations, alloc):

    for r in memAllocations.keys():
        # Relying on a custom comparison
        # function to tell us is one memory
        # range overlaps with another
        #
        if(r == alloc):
            return r;

    return None;

def findMatchingAllocation(memAllocations, memRange):

    for r in memAllocations.keys():
        # Relying on a custom comparison
        # function to tell us is one memory
        # range overlaps with another
        #
        if(r == memRange):
            return memAllocations[r];

    return None;


def parseAlloc(line, out):

    threadID = "<unknown>";
    addr = "<unknown>";
    funcName = "<unknown>";
    size = "<unknown>";
    numItems = "<unknown>";
    sourceLoc = "<unknown>";
    varName = "<unknown>";
    varType = "<unknown>";

    words = line.split(" ");
            
    for i in range(0, len(words)):
        if(i == 0):
            continue;
        if(i == 1):
            threadID = words[i];
        if(i == 2):
            addr = words[i];
        if(i == 3):
            funcName = words[i];
        if(i == 4):
            size = words[i];
        if(i == 5):
            numItems = words[i];
        if(i == 6):
            sourceLoc = words[i];
        if(i == 7):
            varName = words[i];
        if(i == 8):
            varType = words[i];

    
    r = AllocRecord(threadID, addr, funcName, size, numItems,
                sourceLoc, varName, varType);

    out.write(str(r) + "\n");

    # Add this memory allocation to the dictionary
    # First check if one with an overlapping range already exists. 
    # If so, we assume it was freed (we don't track frees yet)
    # and delete it. 
    #
    alloc = MemoryRange(addr, str(int(size) * int(numItems)));
    existingAlloc = findOverlappingAlloc(memAllocations, alloc);

    if(existingAlloc is not None):
        print "Allocation " + str(alloc) + " overlaps with " + str(existingAlloc);
        del memAllocations[existingAlloc];
        
    memAllocations[alloc] = r;


def parseMemoryAccess(line, out):

    accessType = "<unknown>";
    threadID = "<unknown>";
    addr = "<unknown>";
    size = "<unknown>";
    funcName = "<unknown>";
    varName = "<unknown>";
    varType = "<unknown>";
    allocLoc = "<unknown>";


    words = line.split(" ");
            
    for i in range(0, len(words)):
        if(i == 0):
            accessType = words[i].strip(':');
        if(i == 1):
            threadID = words[i];
        if(i == 2):
            addr = words[i];
        if(i == 3):
            size = words[i];
        if(i == 4):
            funcName = words[i];
        if(i == 5):
            varName = words[i];
        if(i == 6):
            varType = words[i];    
        if(i == 7):
            allocLoc = words[i];

    r = AccessRecord(accessType, threadID, addr, size, funcName,
                varName, varType, allocLoc);
    
    if(notValidHex(addr)):
        print "Corrupted record: "
        print line
        return;

    # Let's create a MemoryRange object to see if
    # there is a memory allocation corresponding to
    # this access. If so, we pull the corresponding
    # source location and variable information and 
    # add it to the record
    #
    m = MemoryRange(addr, size);
    allocRecord = findMatchingAllocation(memAllocations, m);

    if(allocRecord is not None):
        r.varName = allocRecord.varName;
        r.varType = allocRecord.varType;
        r.allocLoc = allocRecord.sourceLoc;

    out.write(str(r) + "\n");



def parseFunction(line, out):

    eventType = "";
    threadID = "<unknown>";
    funcName = "<unknown>";
    
    words = line.split(" ");
            
    for i in range(0, len(words)):
        if(i == 0):
            eventType = words[i].strip(':');
        if(i == 1):
            threadID = words[i];
        if(i == 2):
            funcName = words[i];

    r = FuncRecord(eventType, threadID, funcName);

    out.write(str(r) + "\n");
    


def parseLine(line, keepdots, outputstream):

    if(not keepdots):
        if ".plt" in line:
            return

        if ".text" in line:
            return

    line = line.rstrip();

    if line.startswith("alloc:"):
        parseAlloc(line, outputstream);
    if line.startswith("read:") or line.startswith("write:"):
        parseMemoryAccess(line, outputstream);
    if line.startswith("function-begin") or line.startswith("function-end"):
        parseFunction(line, outputstream);



#
# First just parse and convert as-is. Later, we might want to match 
# memory-access records with corresponding allocation records and convert
# memory-access data with the information that the allocation gives us.
#
def parse(fdTrace, keepdots, outputstream):

    for line in fdTrace:
        parseLine(line, keepdots, outputstream);




def parseMyShare(tid, fname, lines, keepdots, startingLine, lastLine):

    counter = 0;

    print ("Process " + str(tid) + " will parse lines "
           + str(startingLine) + " to " + str(lastLine));


    outputstream = open(fname, "w")
    
    # Now process our lines
    for i in range(startingLine, lastLine+1):
        parseLine(lines[i], keepdots, outputstream)
    

    print "Process " + str(tid) + " is done"

def parseWithProcesses(fname, keepdots):

    # Let's find out how many processors we have, so
    # we can use as many processes

    numCPUs = multiprocessing.cpu_count();
    numProcs = numCPUs;

    print "Using " + str(numProcs) + " processes"
    
    fd = open(fname, "r");
    try:
        lines = fd.readlines();
    except:
        print "Failed to read the trace file into memory. It is probably too big."
        print("Please rerun the script without the --usethreads option to parse with "
              + "a single thread");
    fd.close();

    lineNum = len(lines);
    print "Will parse the trace with " +  str(lineNum) + " lines";


    lineShare = int(lineNum) / numProcs;
    catCommand = "cat "

    for i in range(numProcs):
        startingLine = i*lineShare;
        lastLine = -1;

        if(i == numProcs - 1):
            lastLine = int(lineNum)-1;
        else:
            lastLine = i*lineShare + lineShare - 1;

        
        pid = i+1;
        os.mkdir("/tmpfs/mt" + str(pid), 0755); 
        tempFileName = "/tmpfs/mt" + str(pid) + "/tempfile";
        catCommand = catCommand + tempFileName + " "

        p = Process(target=parseMyShare, args=(pid, tempFileName, 
                                               lines, keepdots, startingLine, 
                                               lastLine))
        p.start()
        processes.append(p)

    for p in processes:
        p.join();

    # Consolidate data from all files. 
    catCommand = catCommand + " > " + fname + ".json"
    print "Cat command is:"
    print catCommand
    
    os.system(catCommand);

    for pid in range(numProcs):
        os.system("rm -rf /tmpfs/mt" + str(pid+1))

    print "All done"

    

###
def main():

    parser = argparse.ArgumentParser(description='Convert memtracker trace to JSON.')
    parser.add_argument('--infile', 
                        help='Name of the trace file generated by the memtracker pintool.')
    parser.add_argument('--keepdots', action='store_true', 
                        help='Do not skip records from .text and .plt when generating trace');
    parser.add_argument('--useprocesses', action='store_true', 
                        help='Use multiple processes to parse the data. Do not use this option if the script fails to read all the lines in the file.');


    args = parser.parse_args()
    

    if args.infile is None:
        parse(sys.stdin, args.keepdots);
    else:
        if not os.path.exists(args.infile):
            print 'File ' + args.infile + ' does not exist.';
            sys.exit(1);


        # If we are reading data from the
        # file, let's try to use multiple threads. 
        if args.useprocesses:
            parseWithProcesses(args.infile, args.keepdots);
        else:
            fdTrace = open(args.infile, "r");
            parse(fdTrace, args.keepdots, linenum, sys.stdout);

if __name__ == '__main__':
    main()