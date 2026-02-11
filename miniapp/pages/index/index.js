const { getArticles } = require('../../utils/api');
const { formatDateTime } = require('../../utils/time');

const STATUS_OPTIONS = [
  { value: 'sent', label: '已发送' },
  { value: '', label: '全部' },
  { value: 'failed', label: '失败' },
  { value: 'pending', label: '待发送' }
];

function cleanText(value) {
  return String(value || '').trim();
}

function clipText(value, maxLength) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength)}...`;
}

function normalizeArticle(raw) {
  const zhTitle = cleanText(raw.translated_title) || cleanText(raw.title) || '无标题';
  const enTitle = cleanText(raw.title) || '-';
  const translatedBody = cleanText(raw.translated_summary);
  const originalBody = cleanText(raw.summary);

  return {
    ...raw,
    zhTitle,
    enTitle,
    previewContent: clipText(translatedBody || originalBody || '-', 120),
    hasTranslatedBody: Boolean(translatedBody),
    displayTime: formatDateTime(raw.sent_at || raw.last_attempt_at || raw.created_at)
  };
}

Page({
  data: {
    status: 'sent',
    statusOptions: STATUS_OPTIONS,
    articles: [],
    loading: false,
    errorMessage: ''
  },

  onLoad() {
    this.loadArticles();
  },

  onPullDownRefresh() {
    this.loadArticles({ fromPullDown: true });
  },

  onStatusChange(event) {
    const status = event.currentTarget.dataset.status || '';
    this.setData({ status });
    this.loadArticles();
  },

  onTapArticle(event) {
    const recordKey = event.currentTarget.dataset.recordKey;
    if (!recordKey) {
      return;
    }

    wx.navigateTo({
      url: `/pages/detail/detail?recordKey=${encodeURIComponent(recordKey)}`
    });
  },

  async loadArticles(options = {}) {
    this.setData({ loading: true, errorMessage: '' });

    try {
      const result = await getArticles({
        limit: 20,
        status: this.data.status || undefined
      });
      const items = (result.items || []).map(normalizeArticle);
      this.setData({ articles: items });
    } catch (err) {
      this.setData({
        articles: [],
        errorMessage: `请求失败: ${err.message || 'unknown error'}`
      });
    } finally {
      this.setData({ loading: false });
      if (options.fromPullDown) {
        wx.stopPullDownRefresh();
      }
    }
  }
});
