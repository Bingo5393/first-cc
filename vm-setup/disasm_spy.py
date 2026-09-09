# -*- coding: utf-8 -*-
# 反汇编 spy.dll 指定地址附近代码，用于分析版本检查逻辑（找 patch 点）

import sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

spy_path = r"C:\Users\MAC\AppData\Local\Programs\Python\Python314\Lib\site-packages\wcferry\spy.dll"
data = open(spy_path, "rb").read()
pe = pefile.PE(spy_path)
image_base = pe.OPTIONAL_HEADER.ImageBase


def rva_to_offset(rva):
    for s in pe.sections:
        lo = s.VirtualAddress
        hi = lo + max(s.SizeOfRawData, s.Misc_VirtualSize)
        if lo <= rva < hi:
            return rva - lo + s.PointerToRawData
    return None


def disasm(start_va, end_va):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    start_rva = start_va - image_base
    off = rva_to_offset(start_rva)
    length = end_va - start_va
    code = data[off:off + length]
    for insn in md.disasm(code, start_va):
        # 标记关键点
        mark = ""
        if insn.address == 0x10047ea4:
            mark = "   <<< 引用「不支持当前版本」"
        print(f"0x{insn.address:x}: {insn.mnemonic:8s} {insn.op_str}{mark}")


if __name__ == "__main__":
    start = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x10047d00
    end = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x10047ec0
    disasm(start, end)
