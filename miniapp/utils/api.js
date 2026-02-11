const { API_BASE_URL, API_KEY } = require('../config');

function request(path) {
  const headers = {};
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method: 'GET',
      header: headers,
      timeout: 10000,
      success(res) {
        const ok = res.statusCode >= 200 && res.statusCode < 300;
        if (!ok) {
          reject(new Error(`HTTP ${res.statusCode}`));
          return;
        }
        resolve(res.data || {});
      },
      fail(err) {
        reject(new Error((err && err.errMsg) || 'network error'));
      }
    });
  });
}

function getArticles({ limit = 20, status } = {}) {
  const params = [`limit=${encodeURIComponent(limit)}`];
  if (status) {
    params.push(`status=${encodeURIComponent(status)}`);
  }
  return request(`/api/articles?${params.join('&')}`);
}

function getArticle(recordKey) {
  return request(`/api/articles/${encodeURIComponent(recordKey)}`);
}

module.exports = {
  getArticles,
  getArticle
};
