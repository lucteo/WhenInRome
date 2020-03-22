"""
Description: Tool for determining clang-format settings that best apply to a given source code.

Copyright (c) 2020, Lucian Radu Teodorescu
"""

import sys
import os
import os.path
import argparse
import subprocess
import difflib
import shutil
import copy
from multiprocessing import Pool
import yaml
import json


args = None


def invokeCommandsInParallel(cmds):
    procList = [
        subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for cmd in cmds
    ]
    for proc in procList:
        proc.wait()


def invokeCommandsInParallelCwd(cmdsAndDirs):
    procList = []
    for p in cmdsAndDirs:
        cmd = p[0]
        cwd = p[1]
        # print(cmd, cwd)
        res = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=cwd)
        procList.append(res)
    for proc in procList:
        proc.wait()


class InputSourceCode:
    ''' Responsible for the source code
        Combines the multiple input files into one source file, and allows users to access it.
        Stores details about the input source code
    '''
    baseFilename = ''
    absPath = ''
    ext = ''
    numLines = 0
    dirty = False

    def __init__(self, dumpDir, inputFilenames):
        ''' Prepares the input source code, and gets all relevant data about it. '''
        assert(len(inputFilenames) > 0)
        self.ext = os.path.splitext(inputFilenames[0])[1]

        # Get path of the input file used in all clang-format operations
        self.baseFilename = f'input{self.ext}'
        self.absPath = os.path.abspath(os.path.join(dumpDir, self.baseFilename))

        # Ensure the dump folder exists
        if not os.path.exists(dumpDir):
            os.makedirs(dumpDir)

        # Read the content of the file
        oldContent = []
        try:
            with open(self.absPath, 'r') as f:
                oldContent = f.readlines()
        except:
            pass

        # Generate the input source file
        allLines = []
        separator = ['\n']
        with open(self.absPath, 'w') as outf:
            for inFilename in inputFilenames:
                with open(inFilename, 'r') as inf:
                    content = inf.readlines()
                    outf.writelines(content)
                    allLines.extend(content)
                outf.writelines(separator)
                allLines.extend(separator)
        self.numLines = len(allLines)

        # Check if the input is dirty
        self.dirty = oldContent != allLines


class FileCache:
    ''' Helper class that keeps all the results in a cache on the disk.
        It caches the following information:
            - the style used at every iteration
            - the key of the iterator
            - the formatted code output for each of value of the key
            - the diff files for all the value tried
        The cache has three purposes:
            - allow us to easily spawn file-based operations (clang-format, diff)
            - speed up subsequent runs
            - allow the user to inspect the cache, and based on that change formatting options
    '''

    def __init__(self, dumpDir, inputSC):
        self._dumpDir = dumpDir
        self._iter = 0
        self._cacheDirty = inputSC.dirty
        self._fmtName = f'formatted{inputSC.ext}'

    def startIteration(self, key, baseStyle, values):
        self._iter += 1
        self._ensureIterFolderExists()

        baseStyleStr = json.dumps(baseStyle)

        # Check if the cache is dirty
        if not self._cacheDirty:
            cachedBaseStyle = self._readIterFileContent('baseStyle')
            cachedKey = self._readIterFileContent('key')
            if cachedBaseStyle != baseStyleStr or cachedKey != key:
                self._cacheDirty = True

        # If the cache is dirty, remove all the files from this folder
        if self._cacheDirty:
            dirPath = os.path.join(self._dumpDir, f'iter{self._iter}')
            shutil.rmtree(dirPath)
            self._ensureIterFolderExists()

        # Save the settings for the iteration
        self._writeIterFile('key', key)
        self._writeIterFile('baseStyle', baseStyleStr)

        # Create subfolders for each value
        self.values = {}
        for val in values:
            dirPath = os.path.join(self._dumpDir, f'iter{self._iter}', str(val))
            if not os.path.exists(dirPath):
                os.makedirs(dirPath)

    def getFmtFilename(self, value):
        ''' Get the formatted filename for the given value, for the given base filename '''
        return self._getFullFilename2(str(value), self._fmtName)

    def getLocalFmtFilename(self):
        ''' Returns the name of the formatted file; no folders '''
        return self._fmtName

    def getDiffFilename(self, value):
        ''' Get the diff filename for the given value, for the given base filename '''
        return self._getFullFilename2(str(value), f'formatted.diff')

    def getStyleFilename(self, value):
        ''' Get the .clang-file filename for the given value '''
        return self._getFullFilename2(str(value), f'.clang-format')

    def getValueDir(self, value):
        ''' Returns the directory in which we store files corresponding to a given value '''
        return os.path.join(self._dumpDir, f'iter{self._iter}', str(value))

    def hasFmtCache(self, value):
        ''' Checks if we already have the formatted file for the given value in the cache. '''
        filename = self.getFmtFilename(value)
        return os.path.exists(filename) and os.path.getsize(filename) > 0

    def hasDiffCache(self, value):
        ''' Checks if we already have the diff file for the given value in the cache. '''
        filename = self.getDiffFilename(value)
        return os.path.exists(filename) and os.path.getsize(filename) > 0

    def writeStyleFile(self, value, style):
        ''' Writes to disk the style file for the given value '''
        filename = self.getStyleFilename(value)
        if not os.path.exists(filename):
            content = yaml.dump(style)
            with open(filename, 'w') as f:
                f.write(content)

    def _getFullFilename(self, baseFilename):
        return os.path.join(self._dumpDir, f'iter{self._iter}', baseFilename)

    def _getFullFilename2(self, subdir, baseFilename):
        return os.path.join(self._dumpDir, f'iter{self._iter}', subdir, baseFilename)

    def _readIterFileContent(self, baseFilename):
        ''' Read the content of the given file from the current iteration.
            Return empty if the file is not found.
        '''
        fullPath = self._getFullFilename(baseFilename)
        if os.path.exists(fullPath):
            with open(fullPath) as f:
                content = f.readlines()
                return ''.join(content)
        return ''

    def _writeIterFile(self, baseFilename, content):
        ''' Write an iteration specific file to disk '''
        fullPath = self._getFullFilename(baseFilename)
        with open(fullPath, 'w') as f:
            f.write(content)

    def _ensureIterFolderExists(self):
        fullPath = os.path.join(self._dumpDir, f'iter{self._iter}')
        if not os.path.exists(fullPath):
            os.makedirs(fullPath)


def experimentForOption(inputSC, fileCache, baseStyle, key, values, prevScore):
    print(f'Experimenting for {key}...', end='')
    sys.stdout.flush()

    # Compute names for all the values, and their corresponding styles
    # Names will be keys in the dictionary, and styles will be the the value
    valNamesAndStyles = {}
    for val in values:
        if isinstance(val, dict):
            vkey = list(val.keys())[0]
            vval = list(val.values())[0]
        else:
            vkey = val
            vval = {key: val}
        valNamesAndStyles[vkey] = vval
    valNames = list(valNamesAndStyles.keys())

    # We start another iteration for each key we are experimenting with
    fileCache.startIteration(key, baseStyle, valNames)

    # Run clang-format for all the options
    toRun = []
    for valName in valNames:
        valDict = valNamesAndStyles[valName]
        if not fileCache.hasFmtCache(valName):
            style = copy.deepcopy(baseStyle)
            style.update(valDict)
            fileCache.writeStyleFile(valName, style)
            outFilename = fileCache.getLocalFmtFilename()
            cmd = (f'{args.clangformat}'
                   f' --assume-filename={inputSC.baseFilename} -style=file > {outFilename}')
            cmd = f'cat {inputSC.absPath} | {cmd}'
            cwd = fileCache.getValueDir(valName)
            toRun.append((cmd, cwd))
    invokeCommandsInParallelCwd(toRun)

    # Check the outputs
    for val in valNames:
        if not fileCache.hasFmtCache(val):
            fmtFilename = fileCache.getFmtFilename(val)
            print(f'ERROR: Formated file not generated: {fmtFilename}; invalid option?')
            sys.exit(1)

    # Compute the diffs
    toRun = []
    for val in valNames:
        if not fileCache.hasDiffCache(val):
            fmtFilename = fileCache.getFmtFilename(val)
            diffFilename = fileCache.getDiffFilename(val)
            cmd = f'diff -u {inputSC.absPath} {fmtFilename} > {diffFilename}'
            toRun.append(cmd)
    invokeCommandsInParallel(toRun)

    # Parse the diffs to get the scope
    results = []
    for val in valNames:
        diffFilename = fileCache.getDiffFilename(val)
        cmd = f'grep -e "^[\\+\\-]" {diffFilename} | wc -l'
        res = subprocess.run(cmd, shell=True, capture_output=True)
        diffVal = int(res.stdout.decode('UTF-8'))
        results.append((diffVal, val))

    # Sort the diff values
    results.sort(key=lambda x: x[0])
    minVal = results[0][0]
    maxVal = results[-1][0]
    lowConfidence = minVal > inputSC.numLines
    ignore = minVal == maxVal
    if minVal >= prevScore:
        ignore = True

    if not ignore:
        print(f'\t=> {results[0][1]}', end='')
    else:
        print(f'\t=> ignoring', end='')
    if lowConfidence:
        print(' (low confidence)')
    print('')

    if args.verbose:
        print(f'    diff values: {results} -- range = {maxVal - minVal}')

    if not ignore:
        baseStyle[key] = results[0][1]
    return (baseStyle, minVal)


def main():
    print('WhenInRome, copyright (c) 2020 Lucian Radu Teodorescu\n')

    parser = argparse.ArgumentParser(
        description='Determine clang-format settings that best apply to the given source code')
    parser.add_argument('input', type=str, nargs='+',
                        help='Input file(s) to compute clang-format settings for')
    parser.add_argument('--out', type=str, default='.clang-format',
                        help='Output clang-format rules file')
    parser.add_argument('--clangformat', type=str, metavar='PATH', default='clang-format',
                        help='The path to the clang-format executable')
    parser.add_argument('--options', type=str, metavar='F', default='formatting-options.yml',
                        help='File describing the options to try')
    parser.add_argument('--dumpDir', type=str, default='./tmp',
                        help='If specified, dumps intermediate files there')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='Display more information when running the script')
    global args
    args = parser.parse_args()

    inputSC = InputSourceCode(args.dumpDir, args.input)
    fileCache = FileCache(args.dumpDir, inputSC)

    # Read the options file
    with open(args.options) as f:
        formattingOptions = yaml.safe_load(f)

    # Take the options from top to bottom, and experiment to choose the right value
    baseStyle = {}
    prevScore = inputSC.numLines*4
    for optEntry in formattingOptions:
        (key, values) = list(optEntry.items())[0]
        (baseStype, prevScore) = experimentForOption(inputSC, fileCache, baseStyle, key, values,
                                                     prevScore)

    # Print the resulting formatting options
    print('')
    print('Resulting format rules:')
    print('-----------------------')
    print(yaml.dump(baseStyle))


if __name__ == '__main__':
    main()
