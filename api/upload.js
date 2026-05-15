const crypto = require('crypto');

/**
 * Vercel Blob 클라이언트 토큰 생성 로직 (수동 구현)
 */
function generateClientToken({ blobToken, pathname, callbackUrl, clientPayload }) {
  const tokenWithoutPrefix = blobToken.replace('vercel_blob_rw_', '');
  const [storeId] = tokenWithoutPrefix.split('_');

  const validUntil = new Date();
  validUntil.setMinutes(validUntil.getMinutes() + 30); // 30분 유효

  const payload = JSON.stringify({
    pathname,
    onUploadCompleted: {
      url: callbackUrl || '',
      body: clientPayload || '',
    },
    validUntil: validUntil.toISOString(),
    maximumSizeInBytes: 500 * 1024 * 1024, // 500MB 허용
    allowedContentTypes: [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'application/vnd.ms-powerpoint',
      'application/octet-stream'
    ],
  });

  const hmac = crypto.createHmac('sha256', blobToken);
  hmac.update(payload);
  const signature = hmac.digest('base64');

  return Buffer.from(`${storeId}:${signature}:${payload}`).toString('base64');
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const blobToken = process.env.BLOB_READ_WRITE_TOKEN;
    if (!blobToken) {
      throw new Error('BLOB_READ_WRITE_TOKEN is missing');
    }

    const { type, payload } = req.body;

    if (type === 'blob.generate-client-token') {
      const clientToken = generateClientToken({
        blobToken,
        pathname: payload.pathname,
        callbackUrl: payload.callbackUrl,
        clientPayload: payload.clientPayload,
      });

      return res.status(200).json({
        type: 'blob.generate-client-token',
        clientToken,
      });
    }

    if (type === 'blob.upload-completed') {
      return res.status(200).json({ ok: true });
    }

    return res.status(400).json({ error: `Unknown type: ${type}` });
  } catch (error) {
    console.error('Manual Blob Token Error:', error.message);
    return res.status(500).json({ error: error.message });
  }
};
