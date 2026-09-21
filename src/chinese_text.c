#include "global.h"
#include "text.h"
#include "fonts.h"
#include "chinese_text.h"

// Chinese characters use two bytes.  The unused high-byte ranges mirror the
// encoding introduced by Wokann's Gen III font patch.
bool8 IsChineseChar(u16 currChar, u16 nextChar, u8 fontId, bool32 isJapanese)
{
    if (isJapanese || fontId == FONT_BRAILLE)
        return FALSE;

    return currChar >= 0x01
        && currChar <= 0x1E
        && currChar != 0x06
        && currChar != 0x1B
        && nextChar <= 0xF6;
}

bool8 IsChinesePunctuation(u16 currChar, u8 fontId, bool32 isJapanese)
{
    if (isJapanese || fontId == FONT_BRAILLE)
        return FALSE;

    return currChar == 0x30
        || (currChar >= 0x36 && currChar <= 0x3F && currChar != 0x38);
}

u8 GetChineseGlyphWidth(u16 chineseChar, u8 fontId)
{
    if (fontId == FONT_SMALL || fontId == FONT_SMALL_NARROW)
    {
        if (chineseChar == 0x30 || (chineseChar >= 0x3A && chineseChar <= 0x3E))
            return 5;
        if (chineseChar == 0x37)
            return 6;
        if (chineseChar == 0x39 || chineseChar == 0x3F)
            return 7;
        return 10;
    }

    if (chineseChar == 0x30)
        return 7;
    return 12;
}

void DecompressGlyph_Chinese(u16 chineseChar, u8 fontId)
{
    const u16 *glyphs;
    u16 hi;
    u16 lo;
    u16 glyphId;

    if (IsChinesePunctuation(chineseChar, fontId, FALSE))
    {
        glyphId = chineseChar;
        if (fontId == FONT_SMALL || fontId == FONT_SMALL_NARROW)
            glyphs = gFontSmallLatinGlyphs + 0x20 * glyphId;
        else
            glyphs = gFontNormalLatinGlyphs + 0x20 * glyphId;
    }
    else
    {
        hi = chineseChar >> 8;
        lo = chineseChar & 0xFF;

        // 0x06 and 0x1B are deliberately absent from the high-byte ranges.
        if (hi > 0x1B)
            hi--;
        if (hi > 0x06)
            hi--;
        hi--;
        glyphId = (hi << 8) | lo;

        if (fontId == FONT_SMALL || fontId == FONT_SMALL_NARROW)
            glyphs = gFontSmallChineseGlyphs + 0x20 * glyphId;
        else
            glyphs = gFontNormalChineseGlyphs + 0x20 * glyphId;
    }

    gCurGlyph.width = GetChineseGlyphWidth(chineseChar, fontId);
    gCurGlyph.height = (fontId == FONT_SMALL || fontId == FONT_SMALL_NARROW) ? 13 : 15;
    DecompressGlyphTile(glyphs, gCurGlyph.gfxBufferTop);
    DecompressGlyphTile(glyphs + 0x8, gCurGlyph.gfxBufferTop + 8);
    DecompressGlyphTile(glyphs + 0x10, gCurGlyph.gfxBufferBottom);
    DecompressGlyphTile(glyphs + 0x18, gCurGlyph.gfxBufferBottom + 8);
}

ALIGNED(4) const u16 gFontSmallChineseGlyphs[] =
    INCGFX_U16("graphics/fonts/chinese_small.png", ".latfont");
ALIGNED(4) const u16 gFontNormalChineseGlyphs[] =
    INCGFX_U16("graphics/fonts/chinese_normal.png", ".latfont");
