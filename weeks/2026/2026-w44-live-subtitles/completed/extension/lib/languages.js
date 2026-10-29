// Gemini Live Translate's own language table, checked 2026-10-29.
// https://ai.google.dev/gemini-api/docs/live-api/live-translate#supported-languages
// 78 language entries / 79 codes: Norwegian accepts both no and nb.
export const DEFAULT_TARGET_LANGUAGE = 'zh-Hant';
export const TARGET_LANGUAGES = Object.freeze([
  ['zh-Hant', '繁體中文'], ['zh-Hans', '簡體中文'], ['en', '英文'], ['ja', '日文'], ['ko', '韓文'],
  ['af', '南非語'], ['ak', '阿坎語'], ['sq', '阿爾巴尼亞語'], ['am', '阿姆哈拉語'],
  ['ar', '阿拉伯語'], ['hy', '亞美尼亞語'], ['az', '亞塞拜然語'], ['eu', '巴斯克語'],
  ['be', '白俄羅斯語'], ['bn', '孟加拉語'], ['bg', '保加利亞語'], ['my', '緬甸語'],
  ['ca', '加泰隆尼亞語'], ['hr', '克羅埃西亞語'], ['cs', '捷克語'], ['da', '丹麥語'],
  ['nl', '荷蘭語'], ['et', '愛沙尼亞語'], ['fil', '菲律賓語'], ['fi', '芬蘭語'],
  ['fr', '法文'], ['gl', '加利西亞語'], ['ka', '喬治亞語'], ['de', '德文'],
  ['el', '希臘語'], ['gu', '古吉拉特語'], ['ha', '豪薩語'], ['he', '希伯來語'],
  ['hi', '印地語'], ['hu', '匈牙利語'], ['is', '冰島語'], ['id', '印尼語'],
  ['it', '義大利文'], ['jv', '爪哇語'], ['kn', '卡納達語'], ['kk', '哈薩克語'],
  ['km', '高棉語'], ['rw', '盧安達語'], ['lo', '寮語'], ['lv', '拉脫維亞語'],
  ['lt', '立陶宛語'], ['mk', '馬其頓語'], ['ms', '馬來語'], ['ml', '馬拉雅拉姆語'],
  ['mr', '馬拉地語'], ['mn', '蒙古語'], ['ne', '尼泊爾語'], ['no', '挪威語'],
  ['nb', '挪威語（書面語）'], ['fa', '波斯語'], ['pl', '波蘭語'], ['pt-BR', '葡萄牙語（巴西）'],
  ['pt-PT', '葡萄牙語（葡萄牙）'], ['pa', '旁遮普語'], ['ro', '羅馬尼亞語'], ['ru', '俄文'],
  ['sr', '塞爾維亞語'], ['sd', '信德語'], ['si', '僧伽羅語'], ['sk', '斯洛伐克語'],
  ['sl', '斯洛維尼亞語'], ['es', '西班牙文'], ['su', '巽他語'], ['sw', '斯瓦希里語'],
  ['sv', '瑞典語'], ['ta', '坦米爾語'], ['te', '泰盧固語'], ['th', '泰文'],
  ['tr', '土耳其語'], ['uk', '烏克蘭語'], ['ur', '烏爾都語'], ['uz', '烏茲別克語'],
  ['vi', '越南文'], ['zu', '祖魯語'],
].map(([code, label]) => Object.freeze({ code, label })));
const supported = new Set(TARGET_LANGUAGES.map(language => language.code));
export function normalizeTargetLanguage(value = DEFAULT_TARGET_LANGUAGE) {
  if (!supported.has(value)) throw new Error('請從選單選擇 Gemini Live Translate 支援的目標語言。');
  return value;
}
export function targetLanguageLabel(value) {
  return TARGET_LANGUAGES.find(language => language.code === value)?.label || value;
}
