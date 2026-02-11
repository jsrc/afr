const { getArticle } = require('../../utils/api');
const { formatDateTime } = require('../../utils/time');

function cleanText(value) {
  return String(value || '').trim();
}

function normalizeDetail(raw) {
  const translatedBody = cleanText(raw.translated_summary);
  const originalBody = cleanText(raw.summary);

  return {
    ...raw,
    zhTitle: cleanText(raw.translated_title) || cleanText(raw.title) || '无标题',
    enTitle: cleanText(raw.title) || '-',
    translatedBody,
    originalBody,
    hasTranslatedBody: Boolean(translatedBody),
    displayCreatedAt: formatDateTime(raw.created_at),
    displaySentAt: formatDateTime(raw.sent_at),
    displayLastAttemptAt: formatDateTime(raw.last_attempt_at)
  };
}

Page({
  data: {
    recordKey: '',
    item: null,
    loading: false,
    errorMessage: ''
  },

  onLoad(query) {
    const recordKey = decodeURIComponent((query && query.recordKey) || '');
    this.setData({ recordKey });
    this.loadDetail();
  },

  async loadDetail() {
    if (!this.data.recordKey) {
      this.setData({ errorMessage: 'recordKey is required' });
      return;
    }

    this.setData({ loading: true, errorMessage: '' });

    try {
      const result = await getArticle(this.data.recordKey);
      if (!result.item) {
        throw new Error('empty response');
      }
      this.setData({ item: normalizeDetail(result.item) });
    } catch (err) {
      this.setData({
        item: null,
        errorMessage: `请求失败: ${err.message || 'unknown error'}`
      });
    } finally {
      this.setData({ loading: false });
    }
  }
});
