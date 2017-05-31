#!/usr/bin/env pypy3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (c) 2017, CJ Kucera
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Brute-force solver for CrossCells, since it turns out I don't actually like
# the game much.  We'll see how well this works.

# Running this via PyPy (pypy3 is what I'd used) results in extreme performance
# gains, btw.  On solving level 25, for instance, runtime goes from ~82 seconds
# to ~4 seconds.  Using pypy3, there's only three levels whose solve time is
# unacceptable (27 weeks, 530 years, and 4,242 years, respectively).  Obviously
# the bruteforce approach is insufficient in those cases.  There's a couple of
# the higher levels whose solve times stretch into the 8-minute mark, and one
# which goes to 16 (at worst case - it actually completes in 12).  Times are,
# of course, based on a bit of benchmarking on my own CPU, and may vary
# considerably from system to system.

# Level 43:
#    Whole-board brute force possibilities: 35,184,372,088,832 (26w6d)
#    By-constraint possibilities: 66,822,515,515,617,878,016,000 (299260464y24w)
#
# Level 47:
#    Whole-board brute force possibilities: 36,028,797,018,963,968 (530y19w)
#    By-constraint possibilities: 419,054,904,729,796,608,000,000 (1876711232y9w)
#
# Level 49:
#    Whole-board brute force possibilities: 288,230,376,151,711,744 (4242y50w)
#    By-constraint possibilities: 9,916,281,680,478,901,844,852,736,000,000,000 (44409448502262243328y24w)

# Compiling this via Cython (without any actual Cython optimization) seems to
# cut processing down by about half, which is nice but not as good as PyPy3.  I
# assume Cython would win out if we cdef'd everything and took the time to port
# it over, but I'm not really willing to go through all that work when the real
# gains would come from doing proper logic rather than bruteforce.

import sys
import time
import itertools

class OperatorCell(object):
    """
    A simple number-operation cell.  (AFAIK at the moment, ALL
    cells are simple number operations, but maybe there are more
    kinds coming up.)
    """

    def label(self):
        """
        How we should be printed
        """
        if self.active:
            return '{}{:<2}'.format(self.disp_char, self.number)
        else:
            return '---'

class AddCell(OperatorCell):
    """
    A single cell which adds
    """

    disp_char = '+'

    def __init__(self, number, idx):
        self.number = number
        self.active = False
        self.idx = idx

    def hit(self, total):
        """
        Performs our action if we're hit
        """
        return total + self.number

class MultiplyCell(OperatorCell):
    """
    A single cell which multiplies
    """

    disp_char = '*'

    def __init__(self, number, idx):
        self.number = number
        self.active = False
        self.idx = idx

    def hit(self, total):
        """
        Performs our action if we're hit
        """
        return total * self.number

class Constraint(object):
    """
    Base Constraint class
    """

    def get_valid_masks(self):
        """
        Gets a list of valid masks which are acceptable here.  Basically we do
        a little brute-force solve across ONLY the cells that this constraint
        involves, and return a list of masks describing the possibilities.
        This is used for our by-constraint method, which uses a pair of
        bitmasks for each constraint to define which cells should be on
        (`mask`), and which should be off (`inv_mask`).  By using
        `itertools.product()` across the range of possible constraints, we can
        do bitwise tests to find out which set of possibilities work with each
        other.  Often this method is quite a bit faster than a brute-force
        method across the entire puzzle space, but when the number of
        constraints grows it's often the other way around.
        """
        masks = []

        total_cells = len(self.cells)
        total_choices = 2**(total_cells)
        for num in range(total_choices):
            for bitnum in range(total_cells):
                if ((num >> bitnum) & 0x1) == 1:
                    self.cells[bitnum].active = True
                else:
                    self.cells[bitnum].active = False
            if self.check():
                mask = 0
                inv_mask = 0
                for cell in self.cells:
                    if cell.active:
                        mask = (mask | (1 << cell.idx))
                    else:
                        inv_mask = (inv_mask | (1 << cell.idx))
                masks.append((mask, inv_mask))
        return masks

class TotalConstraint(Constraint):
    """
    Constraint which enforces a total on a line
    """
    
    def __init__(self, total):
        self.total = total
        self.cells = []
    
    def check(self):
        total = 0
        for cell in self.cells:
            if cell.active:
                total = cell.hit(total)
        if total == self.total:
            return True
        else:
            return False

class CountConstraint(Constraint):
    """
    Constraint which enforces a certain number of active cells
    on a line
    """

    def __init__(self, count):
        self.count = count
        self.cells = []

    def check(self):
        count = 0
        for cell in self.cells:
            if cell.active:
                count += 1
        if count == self.count:
            return True
        else:
            return False

class App(object):
    """
    Main solver class
    """

    def __init__(self, filename):
        self.width = None
        self.height = None
        self.cells = []
        self.rows = []
        self.cols = []
        self.constraints = []
        self.grid = []

        with open(filename, 'r') as df:

            # First read the size of the level
            size = df.readline().strip()
            (width, height) = [int(n) for n in size.split('x')]
            self.width = width
            self.height = height
            for w in range(width):
                self.cols.append([])
            for h in range(height):
                self.rows.append([])
            for y in range(height):
                self.grid.append([])
                for x in range(width):
                    self.grid[y].append(None)

            # Now read cells
            cellidx = 0
            while True:
                line = df.readline().strip()
                if line == '--':
                    break
                elif line == '' or line[0] == '#':
                    # Allow for some whitespace and comments, for legibility
                    continue
                (coords, definition) = line.split(': ')
                (x, y) = [int(n) for n in coords.split(',')]

                if definition[0] == '+':
                    cell = AddCell(int(definition[1:]), cellidx)
                elif definition[0] == '*':
                    cell = MultiplyCell(int(definition[1:]), cellidx)
                else:
                    raise Exception('Unknown cell prefix: {}'.format(definition[0]))
                self.cols[x].append(cell)
                self.rows[y].append(cell)
                self.grid[y][x] = cell
                self.cells.append(cell)
                cellidx += 1

            # And finally constraints
            line = df.readline().strip()
            while line:
                if line == '' or line[0] == '#':
                    line = df.readline().strip()
                    continue
                (positiondef, constraintdef) = line.split(': ')
                (postype, posnum) = positiondef.split('_')
                posnum = int(posnum)
                if postype == 'total' or postype == 'count':
                    cell_list_str = constraintdef.split(' ')
                    cell_list = []
                    for strdef in cell_list_str:
                        (x, y) = [int(n) for n in strdef.split(',')]
                        cell_list.append(self.grid[y][x])
                    if postype == 'total':
                        cons = TotalConstraint(posnum)
                    else:
                        cons = CountConstraint(posnum)
                    cons.cells = cell_list
                else:
                    (constype, consnum) = constraintdef.split('_')

                    if constype == 'total':
                        cons = TotalConstraint(int(consnum))
                    elif constype == 'count':
                        cons = CountConstraint(int(consnum))
                    else:
                        raise Exception('Unknown constraint type: {}'.format(constype))

                    if postype == 'row':
                        cons.cells = self.rows[posnum]
                    elif postype == 'col':
                        cons.cells = self.cols[posnum]
                    elif postype == 'rowrev':
                        cons.cells = list(reversed(self.rows[posnum]))
                    elif postype == 'colrev':
                        cons.cells = list(reversed(self.cols[posnum]))
                    else:
                        raise Exception('Unknown constraint positioning: {}'.format(postype))

                self.constraints.append(cons)
                line = df.readline().strip()

    def seconds_to_string(self, seconds):
        """
        Converts a value in seconds to a more human-readable form.
        """
        if seconds < 60:
            return '{}s'.format(int(seconds))
        (minutes, seconds) = divmod(seconds, 60)
        if minutes < 60:
            return '{}m{}s'.format(int(minutes), int(seconds))
        (hours, minutes) = divmod(minutes, 60)
        if hours < 24:
            return '{}h{}m'.format(int(hours), int(minutes))
        (days, hours) = divmod(hours, 24)
        if days < 7:
            return '{}d{}h'.format(int(days), int(hours))
        (weeks, days) = divmod(days, 7)
        if weeks < 52:
            return '{}w{}d'.format(int(weeks), int(days))
        (years, weeks) = divmod(weeks, 52)
        return '{}y{}w'.format(int(years), int(weeks))

    def solve(self):
        """
        Solve.  A couple of different methods here - which one is used will depend
        on how efficient we think the other will be.  The "whole-board brute force"
        method is pretty self-explanatory.  For a bit of a description of what I'm
        calling "by-constraint," see `Constraint.get_valid_masks()` (and, of course,
        the relevant block, below).
        """

        # Some data
        total_cells = len(self.cells)
        brute_choices = 2**(total_cells)
        masks = []
        for cons in self.constraints:
            masks.append(cons.get_valid_masks())
        constraint_choices = 1
        for mask_choice in masks:
            constraint_choices *= len(mask_choice)

        # These numbers based on a pretty small handful of runs, but I'd
        # expect them to be reasonably accurate.  Of course this depends on
        # what kind of CPU we're running on - these are good for my own desktop
        # but could vary significantly.  I'd *expect* that the ratio of time
        # spent per method is probably the same, though, so even if the time
        # estimates are wrong, hopefully it still makes a reasonable choice as
        # to which one to try.
        possibilities_per_second_constraint = 7100000
        possibilities_per_second_brute = 2160000
        seconds_constraint = constraint_choices / possibilities_per_second_constraint
        seconds_brute = brute_choices / possibilities_per_second_brute

        print('')
        print('Solving for puzzle with {} cells, {} constraints'.format(total_cells, len(self.constraints)))
        print('  Whole-board brute force possibilities: {:,} ({})'.format(
            brute_choices, self.seconds_to_string(seconds_brute)))
        print('            By-constraint possibilities: {:,} ({})'.format(
            constraint_choices, self.seconds_to_string(seconds_constraint)))
        print('')

        min_seconds = min(seconds_brute, seconds_constraint)
        if min_seconds > (60*60):
            print('Aborting solving - need a better method for this level.')
            print('')
            return

        start_time = time.time()
        if seconds_constraint < seconds_brute:

            print('Solving by individual constraints first')
            print('')

            all_ones = 0
            for bitnum in range(total_cells):
                all_ones |= (1 << bitnum)
            for (idx, mask_choice) in enumerate(itertools.product(*masks)):
                idx += 1
                total_mask = 0
                total_inv_mask = 0
                for (mask, inv_mask) in mask_choice:
                    total_mask |= mask
                    total_inv_mask |= inv_mask
                if (total_mask ^ total_inv_mask) == all_ones:
                    for bitnum in range(total_cells):
                        if ((total_mask >> bitnum) & 0x1) == 1:
                            self.cells[bitnum].active = True
                        else:
                            self.cells[bitnum].active = False
                    print('Found solution on try {:,} ({}):'.format(
                        idx+1, self.seconds_to_string(time.time() - start_time)))
                    print('')
                    self.print_state()
                    break

        else:

            print('Solving by whole-board bruteforce')
            print('')

            for num in range(brute_choices):
                for bitnum in range(total_cells):
                    if ((num >> bitnum) & 0x1) == 1:
                        self.cells[bitnum].active = True
                    else:
                        self.cells[bitnum].active = False
                solved = True
                for constraint in self.constraints:
                    if not constraint.check():
                        solved = False
                        break
                if solved:
                    print('Found solution on try {:,} ({})'.format(
                        num+1, self.seconds_to_string(time.time() - start_time)))
                    print('')
                    self.print_state()
                    break

        print('')

    def print_state(self):
        """
        Prints what the level looks like.
        """
        for y in range(self.height):
            for x in range(self.width):
                cell = self.grid[y][x]
                if cell:
                    sys.stdout.write(cell.label())
                else:
                    sys.stdout.write('   ')
                sys.stdout.write(' ')
            sys.stdout.write("\n")

if __name__ == '__main__':

    if len(sys.argv) != 2:
        print('Specfiy exactly one filename as an argument')
        sys.exit(1)
    filename  = sys.argv[1]

    app = App(filename)
    app.solve()
