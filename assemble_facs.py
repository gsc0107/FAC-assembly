#!/usr/bin/env python

import sys
import os
import argparse
import subprocess
import shutil
import datetime
import platform

#setup menu with argparse
class MyFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, prog):
        super(MyFormatter, self).__init__(prog, max_help_position=48)
parser = argparse.ArgumentParser(prog='assemble_facs.py',
    description = '''Script to quality trim, subtract vector reads, and assemble using unicyler''',
    epilog = """Written by Jon Palmer (2018) nextgenusfs@gmail.com""",
    formatter_class = MyFormatter)
parser.add_argument('-v', '--vector', required=True, help='FASTA vector sequence')
parser.add_argument('-1', '--forward', required=True, help='FASTQ R1')
parser.add_argument('-2', '--reverse', required=True, help='FASTQ R2')
parser.add_argument('-c', '--cpus', default=8, type=int, help='Number of CPUS')
args=parser.parse_args()

def which_path(file_name):
    for path in os.environ["PATH"].split(os.pathsep):
        full_path = os.path.join(path, file_name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK):
            return full_path
    return None

#get basename
if '_' in os.path.basename(args.forward):
	base = os.path.basename(args.forward).split('_')[0]
else:
	base = os.path.basename(args.forward).split('.',-1)[0]

#get compression threads
bamcpus = args.cpus // 2

#generate logfile
logfile = base + '_assemble_facs.log'
if os.path.isfile(logfile):
	os.remove(logfile)

print('------------------------------------------')
print('[{:}] Running Python v{:} '.format(datetime.datetime.now().strftime('%b %d %I:%M %p'), platform.python_version()))
dependencies = ['trim_galore', 'minimap2', 'samtools', 'unicycler']
for x in dependencies:
	if not which_path(x):
		print('{:} is not properly installed, install and re-run script'.format(x))
		sys.exit(1)

with open(logfile, 'w') as log:
	#quality/adapter filter
	print('[{:}] Trimming adapters from reads using Trim Galore'.format(datetime.datetime.now().strftime('%b %d %I:%M %p')))
	cmd = ['trim_galore', '--paired', '--quality', '10', os.path.abspath(args.forward), os.path.abspath(args.reverse)]
	subprocess.call(cmd, stderr=log, stdout=log)
	qualR1 = os.path.basename(args.forward).split('.f')[0]
	qualR1 = qualR1+'_val_1.fq.gz'
	qualR2 = os.path.basename(args.reverse).split('.f')[0]
	qualR2 = qualR2+'_val_2.fq.gz'

	#map the reads to the vector using minimap2
	print('[{:}] Mapping reads to vector using minimap2'.format(datetime.datetime.now().strftime('%b %d %I:%M %p')))
	cmd = ['minimap2', '-ax', 'sr', '-t', str(args.cpus), os.path.abspath(args.vector), qualR1, qualR2]
	SAM = base+'_minimap2_align.sam'
	BAM1 = base +'_minimap2_align.bam'
	with open(SAM, 'w') as output:
		subprocess.call(cmd, stdout=output, stderr=log)
	with open(BAM1, 'w') as output:
		subprocess.call(['samtools', 'view', '-bS', '-@', str(bamcpus), SAM], stdout=output, stderr=log)
	cleanR1 = base+'_clean_R1.fastq.gz'
	cleanR2 = base+'_clean_R2.fastq.gz'
	print('[{:}] Extracting unmapped reads using Samtools (samtools fastq -F 0x2)'.format(datetime.datetime.now().strftime('%b %d %I:%M %p')))
	cmd = ['samtools', 'fastq', '-1', cleanR1, '-2', cleanR2, '-@', str(bamcpus), '-F', '0x2', BAM1]
	subprocess.call(cmd, stderr=log)
	os.remove(SAM)
	os.remove(BAM1)

	#now run unicycler
	print('[{:}] Assembling with Unicycler'.format(datetime.datetime.now().strftime('%b %d %I:%M %p')))
	cmd = ['unicycler', '-t', str(args.cpus), '--min_fasta_length', '1000', '--linear_seqs', '60', '-1', cleanR1, '-2', cleanR2, '-o', base+'_unicycler']
	subprocess.call(cmd)
	assembly = base+'_unicycler.fasta'
	with open(assembly, 'w') as outfile:
		with open(os.path.join(base+'_unicycler', 'assembly.fasta'), 'rU') as infile:
			for line in infile:
				if line.startswith('>'):
					line = line.replace('>', '>ctg')
				outfile.write(line)
	print('[{:}] Unicycler finished, final output assembly: {:}'.format(datetime.datetime.now().strftime('%b %d %I:%M %p'), assembly))
	print('[{:}] Logfile: {:}'.format(datetime.datetime.now().strftime('%b %d %I:%M %p'), logfile))
print('------------------------------------------')