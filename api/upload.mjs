import { generateClientTokenFromReadWriteToken } from '@vercel/blob/client';

export default async function handler(request, response) {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (request.method === 'OPTIONS') return response.status(200).end();

  try {
    const token = process.env.BLOB_READ_WRITE_TOKEN;
    if (!token) throw new Error('BLOB_READ_WRITE_TOKEN is missing');

    const { type, payload } = request.body;

    if (type === 'blob.generate-client-token') {
      // SDK의 저수준 함수를 사용하여 토큰만 깔끔하게 생성합니다.
      const clientToken = await generateClientTokenFromReadWriteToken({
        token,
        pathname: payload.pathname,
        onBeforeGenerateToken: async () => ({
          allowedContentTypes: [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint',
            'application/octet-stream'
          ],
        }),
      });

      return response.status(200).json({ clientToken });
    }

    return response.status(400).json({ error: 'Invalid request type' });
  } catch (error) {
    console.error('SERVER ERROR:', error.message);
    return response.status(400).json({ message: error.message });
  }
}
