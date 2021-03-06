import os
import sys
import time
from unittest2 import skipIf

from circus.process import Process, RUNNING
from circus.tests.support import TestCircus


RLIMIT = """\
import resource, sys

with open(sys.argv[1], 'w') as f:
    for limit in ('NOFILE', 'NPROC'):
        res = getattr(resource, 'RLIMIT_%s' % limit)
        f.write('%s=%s\\n' % (limit, resource.getrlimit(res)))
"""


VERBOSE = """\
import sys


for i in range(1000):
    for stream in (sys.stdout, sys.stderr):
        stream.write(str(i))
        stream.flush()

"""


class TestProcess(TestCircus):

    def test_base(self):
        cmd = sys.executable
        args = "-c 'import time; time.sleep(2)'"
        process = Process('test', cmd, args=args, shell=False)
        try:
            info = process.info()
            self.assertEqual(process.pid, info['pid'])
            age = process.age()
            self.assertTrue(age > 0.)
            self.assertFalse(process.is_child(0))
        finally:
            process.stop()

    def test_rlimits(self):
        script_file = self.get_tmpfile(RLIMIT)
        output_file = self.get_tmpfile()

        cmd = sys.executable
        args = [script_file, output_file]
        rlimits = {'nofile': 20,
                   'nproc': 20}

        process = Process('test', cmd, args=args, rlimits=rlimits)
        # wait for the process to finish
        while process.status == RUNNING:
            time.sleep(1)

        f = open(output_file, 'r')
        output = {}
        for line in f.readlines():
            limit, value = line.rstrip().split('=', 1)
            output[limit] = value
        f.close()

        def srt2ints(val):
            return [long(key) for key in val[1:-1].split(',')]

        wanted = [20L, 20L]

        self.assertEqual(srt2ints(output['NOFILE']), wanted)
        self.assertEqual(srt2ints(output['NPROC']), wanted)

    def test_comparison(self):
        cmd = sys.executable
        args = ['import time; time.sleep(2)', ]
        p1 = Process('1', cmd, args=args)
        p2 = Process('2', cmd, args=args)

        self.assertTrue(p1 < p2)
        self.assertFalse(p1 == p2)
        self.assertTrue(p1 == p1)

        p1.stop()
        p2.stop()

    def test_process_parameters(self):
        # all the options passed to the process should be available by the
        # command / process

        p1 = Process('1', 'make-me-a-coffee',
                     '$(circus.wid) --type $(circus.env.type)',
                     shell=False, spawn=False, env={'type': 'macchiato'})

        self.assertEquals(['make-me-a-coffee', '1', '--type', 'macchiato'],
                          p1.format_args())

        p2 = Process('1', 'yeah $(CIRCUS.WID)', spawn=False)
        self.assertEquals(['yeah', '1'], p2.format_args())

        os.environ['coffee_type'] = 'american'
        p3 = Process('1', 'yeah $(circus.env.type)', shell=False, spawn=False,
                     env={'type': 'macchiato'})
        self.assertEquals(['yeah', 'macchiato'], p3.format_args())
        os.environ.pop('coffee_type')

    @skipIf(not hasattr(sys.stdout, 'fileno'), 'Nose runs without -s')
    def test_streams(self):
        script_file = self.get_tmpfile(VERBOSE)
        cmd = sys.executable
        args = [script_file]

        # 1. streams sent to /dev/null
        process = Process('test', cmd, args=args, close_child_stdout=True,
                          close_child_stderr=True)

        # wait for the process to finish
        while process.status == RUNNING:
            time.sleep(1)

        # the pipes should be empty
        self.assertEqual(process.stdout.read(), '')
        self.assertEqual(process.stderr.read(), '')

        # 2. streams sent to /dev/null, no PIPEs
        process = Process('test', cmd, args=args, close_child_stdout=True,
                          close_child_stderr=True, pipe_stdout=False,
                          pipe_stderr=False)

        # wait for the process to finish
        while process.status == RUNNING:
            time.sleep(1)

        # the pipes should be unexistant
        self.assertTrue(process.stdout is None)
        self.assertTrue(process.stderr is None)

        # 3. streams & pipes open
        process = Process('test', cmd, args=args)

        # wait for the process to finish
        while process.status == RUNNING:
            time.sleep(1)

        # the pipes should be unexistant
        self.assertEqual(len(process.stdout.read()), 2890)
        self.assertEqual(len(process.stderr.read()), 2890)
