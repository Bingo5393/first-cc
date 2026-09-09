# -*- coding: utf-8 -*-
# 分析 spy.dll：解析 PE 节区 + 定位关键字符串 + 找代码段里对字符串地址的引用(xref)
# 目的：找到 spy.dll 读微信版本号失败、报「不支持当前版本」的检查代码，为 patch 做准备。

import pefile

spy_path = r"C:\Users\MAC\AppData\Local\Programs\Python\Python314\Lib\site-packages\wcferry\spy.dll"
data = open(spy_path, "rb").read()

pe = pefile.PE(spy_path)
image_base = pe.OPTIONAL_HEADER.ImageBase
print("ImageBase:", hex(image_base))
print("入口点 RVA:", hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint))
print("Machine:", hex(pe.FILE_HEADER.Machine), "(0x14c=32位x86)" if pe.FILE_HEADER.Machine == 0x14c else "")
print()
print("=== 节区 ===")
for s in pe.sections:
    name = s.Name.decode('utf-8', 'ignore').strip('\x00')
    print(f"  {name:8s} VA={hex(s.VirtualAddress):>10}  raw={hex(s.PointerToRawData):>10}  rawsize={hex(s.SizeOfRawData)}")


def rva_to_offset(rva):
    for s in pe.sections:
        lo = s.VirtualAddress
        hi = lo + max(s.SizeOfRawData, s.Misc_VirtualSize)
        if lo <= rva < hi:
            return rva - lo + s.PointerToRawData
    return None


def offset_to_rva(off):
    for s in pe.sections:
        lo = s.PointerToRawData
        hi = lo + s.SizeOfRawData
        if lo <= off < hi:
            return off - lo + s.VirtualAddress
    return None


# 关键字符串（ASCII 与 GBK）
targets = {
    "WeChatWin.dll": b"WeChatWin.dll",
    "3.9.12.56": b"3.9.12.56",
    "不支持当前版本": "不支持当前版本".encode("gbk"),
    "WeChat version": b"WeChat version",
    "spy.cpp": b"spy.cpp",
}

print()
print("=== 字符串定位 ===")
str_vas = {}
for name, pat in targets.items():
    idx = 0
    found = []
    while True:
        idx = data.find(pat, idx)
        if idx == -1:
            break
        rva = offset_to_rva(idx)
        if rva is not None:
            found.append((idx, rva))
        idx += 1
    if found:
        for off, rva in found:
            va = image_base + rva
            print(f"  {name}: file={hex(off)}  rva={hex(rva)}  va={hex(va)}")
            str_vas.setdefault(name, []).append(rva)
    else:
        print(f"  {name}: (未找到)")

# 找 .text 段，在里面搜索对字符串 VA 的引用（push imm32 常见，小端 4 字节）
print()
print("=== xref：代码段里对字符串地址的引用 ===")
text = None
for s in pe.sections:
    if b".text" in s.Name or s.Name.decode('utf-8', 'ignore').strip('\x00') == ".text":
        text = s
        break
if text is None:
    print("(未找到 .text 段)")
else:
    text_data = data[text.PointerToRawData: text.PointerToRawData + text.SizeOfRawData]
    text_va_base = image_base + text.VirtualAddress
    import struct
    for name, vas in str_vas.items():
        for va in vas:
            va_full = image_base + va
            pattern = struct.pack("<I", va_full)
            off = 0
            while True:
                off = text_data.find(pattern, off)
                if off == -1:
                    break
                rva = text.VirtualAddress + off
                va_site = image_base + rva
                print(f"  {name} 的地址 {hex(va_full)} 在 {hex(va_site)} 被引用（file={hex(text.PointerToRawData + off)}）")
                off += 1
