#ifndef GUARD_CHINESE_TEXT_H
#define GUARD_CHINESE_TEXT_H

bool8 IsChineseChar(u16 currChar, u16 nextChar, u8 fontId, bool32 isJapanese);
bool8 IsChinesePunctuation(u16 currChar, u8 fontId, bool32 isJapanese);
void DecompressGlyph_Chinese(u16 chineseChar, u8 fontId);
u8 GetChineseGlyphWidth(u16 chineseChar, u8 fontId);

extern const u16 gFontSmallChineseGlyphs[];
extern const u16 gFontNormalChineseGlyphs[];

#endif // GUARD_CHINESE_TEXT_H
