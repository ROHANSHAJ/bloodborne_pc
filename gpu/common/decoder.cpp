// SPDX-License-Identifier: GPL-2.0-or-later
#include <algorithm>

#include "common/decoder.h"

namespace Common {

DecoderImpl::DecoderImpl() {
    ZydisDecoderInit(&decoder, ZYDIS_MACHINE_MODE_LONG_64, ZYDIS_ADDRESS_WIDTH_64);
    ZydisFormatterInit(&formatter, ZYDIS_FORMATTER_STYLE_INTEL);
}

std::string DecoderImpl::disassembleInst(ZydisDecodedInstruction& inst,
                                         ZydisDecodedOperand*, u64 address) {
    char text[256];
    ZydisFormatterFormatInstruction(&formatter, &inst, text, sizeof(text), address);
    return text;
}

ZyanStatus DecoderImpl::decodeInstruction(ZydisDecodedInstruction& inst,
                                          ZydisDecodedOperand* operands, void* data, u64 size) {
    const ZyanStatus status = ZydisDecoderDecodeBuffer(&decoder, data, size, &inst);
    if (ZYAN_SUCCESS(status)) {
        std::copy_n(inst.operands, inst.operand_count, operands);
    }
    return status;
}

} // namespace Common
