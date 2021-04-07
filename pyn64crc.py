# 2021/02/17: Python (3.2) rewrite, by Hextator, of
# http://n64dev.org/n64crc.html
# 2010/03/23: addition by spinout to actually fix CRC if it is incorrect

# Copyright notice for this file:
#  Copyright (C) 2005 Parasyte

# Based on uCON64's N64 checksum algorithm by Andreas Sterbenz

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# https://www.gnu.org/licenses/old-licenses/gpl-2.0.html

import os
import sys

usage = 'Usage: "pyn64crc.py" inFilePath'

N64_HEADER_SIZE        = 0x40
N64_BC_SIZE            = (0x1000 - N64_HEADER_SIZE)

N64_CRC1_OFFSET        = 0x00000010
N64_CRC2_OFFSET        = 0x00000014

CHECKSUM_START         = 0x00001000
CHECKSUM_LENGTH        = 0x00100000
CHECKSUM_CIC6102       = 0xF8CA4DDC
CHECKSUM_CIC6103       = 0xA3886759
CHECKSUM_CIC6105       = 0xDF26F436
CHECKSUM_CIC6106       = 0x1FEA617A

def truncTo32(val):
	return val & 0xFFFFFFFF

def rotateLeft(value, bits):
	return truncTo32((value << (bits)) | (value >> (32 - (bits))))

# Big endian
def byteListToInt32(inList):
	return truncTo32(inList[0] << 24 | inList[1] << 16 | inList[2] <<  8 | inList[3])

# Big endian
def write32ToList(targetList, index, data):
	targetList[index] = (data & 0xFF000000) >> 24
	targetList[index + 1] = (data & 0x00FF0000) >> 16
	targetList[index + 2] = (data & 0x0000FF00) >> 8
	targetList[index + 3] = (data & 0x000000FF)

CRC_TABLE_SIZE = 256
CRCtable = list([0 for i in range(256)])

def genCRCtable():
	global CRCtable

	crc = None
	poly = 0xEDB88320

	for i in range(256):
		crc = i
		for j in range(8, 0, -1):
			if crc & 1:
				crc = (crc >> 1) ^ poly
			else:
				crc >>= 1
		CRCtable[i] = crc

# Moved from main entry point
# Essentially treating this list as a constant
# Init CRC algorithm
genCRCtable()

def crc32(data, length):
	crc = truncTo32(~0)

	for i in range(length):
		crc = truncTo32((crc >> 8) ^ CRCtable[(crc ^ data[i]) & 0xFF])

	return truncTo32(~crc)

def N64GetCIC(data):
	global N64_HEADER_SIZE
	global N64_BC_SIZE

	crcSection = data[N64_HEADER_SIZE:N64_HEADER_SIZE + N64_BC_SIZE]
	length = N64_BC_SIZE
	crcResult = crc32(crcSection, length)
	if 0x6170A4A1 == crcResult:
		return 6101
	elif 0x90BB6CB5 == crcResult:
		return 6102
	elif 0x0B050EE0 == crcResult:
		return 6103
	elif 0x98BC2C86 == crcResult:
		return 6105
	elif 0xACC8580A == crcResult:
		return 6106

	print('Error identifying CIC; defaulting to CIC-NUS-6105\n')
	return 6105

def N64CalcCRC(data, crcTuple):
	global N64_HEADER_SIZE
	global CHECKSUM_START
	global CHECKSUM_LENGTH
	global CHECKSUM_CIC6102
	global CHECKSUM_CIC6103
	global CHECKSUM_CIC6105
	global CHECKSUM_CIC6106

	bootcode = N64GetCIC(data)
	seed = None

	if 6101 == bootcode or 6102 == bootcode:
		seed = CHECKSUM_CIC6102
	elif 6103 == bootcode:
		seed = CHECKSUM_CIC6103
	elif 6105 == bootcode:
		seed = CHECKSUM_CIC6105
	elif 6106 == bootcode:
		seed = CHECKSUM_CIC6106
	else:
		return 1

	t1 = t2 = t3 = t4 = t5 = t6 = t7 = seed

	r = None
	d = None

	for index in range(CHECKSUM_START, CHECKSUM_START + CHECKSUM_LENGTH, 4):
		d = byteListToInt32(data[index:index + 4])
		if truncTo32(t6 + d) < t6:
			t4 += 1
		t6 = truncTo32(t6 + d)
		t3 = truncTo32(t3 ^ d)
		r = rotateLeft(d, (d & 0x1F))
		t5 = truncTo32(t5 + r)
		if t2 > d:
			t2 = truncTo32(t2 ^ r)
		else:
			t2 = truncTo32(t2 ^ truncTo32(t6 ^ d))

		if 6105 == bootcode:
			intIndex = N64_HEADER_SIZE + 0x0710 + (index & 0xFF)
			t7 = byteListToInt32(data[intIndex:intIndex + 4])
			t1 = truncTo32(t1 + truncTo32(t7 ^ d))
		else:
			t1 = truncTo32(t1 + truncTo32(t5 ^ d))

	if 6103 == bootcode:
		crcTuple[0] = truncTo32(truncTo32(t6 ^ t4) + t3)
		crcTuple[1] = truncTo32(truncTo32(t5 ^ t2) + t1)
	elif 6106 == bootcode:
		crcTuple[0] = truncTo32(truncTo32(t6 * t4) + t3)
		crcTuple[1] = truncTo32(truncTo32(t5 * t2) + t1)
	else:
		crcTuple[0] = truncTo32(truncTo32(t6 ^ t4) ^ t3)
		crcTuple[1] = truncTo32(truncTo32(t5 ^ t2) ^ t1)

	return 0

def main(args):
	global N64_CRC1_OFFSET
	global N64_CRC2_OFFSET
	global CHECKSUM_START
	global CHECKSUM_LENGTH

	# Process argument(s)
	argc = len(args)
	if argc < 2 or argc > 2:
		print(usage)
		raise Exception('Usage error')
	inFilePath = args[1]

	# Read ROM
	rom = []
	with open(inFilePath, 'rb') as inFile:
		rom = inFile.read()
		rom = list(rom)
	if not rom:
		raise Exception('Unable to open ' + inFilePath)

	# Check CIC BootChip
	cic = N64GetCIC(rom)
	cicName = 'Unknown'
	if cic:
		cicName = 'CIC-NUS-' + str(cic)
	print("BootChip: " + cicName + '\n')

	# Calculate CRC
	# Implemented as a list, because whatever
	crcTuple = [0, 0]
	if N64CalcCRC(rom, crcTuple):
		print("Unable to calculate CRC\n")
		return

	# Check 1st CRC
	origCRC1 = byteListToInt32(rom[N64_CRC1_OFFSET:N64_CRC1_OFFSET + 4])
	print('CRC 1: 0x{crc:08X}\n'.format(crc = origCRC1))
	print('Calculated CRC 1: 0x{crc:08X}\n'.format(crc = crcTuple[0]))
	if crcTuple[0] == origCRC1:
		print('(Good)\n')
	else:
		write32ToList(rom, N64_CRC1_OFFSET, crcTuple[0])
		print('(Bad, fixed)\n')

	# Check 2nd CRC
	origCRC2 = byteListToInt32(rom[N64_CRC2_OFFSET:N64_CRC2_OFFSET + 4])
	print('CRC 2: 0x{crc:08X}\n'.format(crc = origCRC2))
	print('Calculated CRC 2: 0x{crc:08X}\n'.format(crc = crcTuple[1]))
	if crcTuple[0] == origCRC2:
		print('(Good)\n')
	else:
		write32ToList(rom, N64_CRC2_OFFSET, crcTuple[1])
		print('(Bad, fixed)\n')

	# Write ROM (with updated CRCs, if applicable)
	with open(inFilePath, 'wb') as outFile:
		if rom:
			outFile.write(bytes(rom))

if __name__ == '__main__': main(sys.argv)
