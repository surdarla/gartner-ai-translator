import { generateClientTokenFromReadWriteToken } from '@vercel/blob/client';

export default async function handler(request, response) {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (request.method === 'OPTIONS') return response.status(200).end();

  try {
    const token = process.env.BLOB_READ_WRITE_TOKEN || process.env.VERCEL_BLOB_READ_WRITE_TOKEN;
    if (!token) throw new Error('환경변수(BLOB_READ_WRITE_TOKEN)가 설정되지 않았습니다.');

    const { payload } = request.body;

    // Vercel이 요구하는 규격의 클라이언트 토큰 생성
    const clientToken = await generateClientTokenFromReadWriteToken({
      token,
      pathname: payload.pathname,
      onBeforeGenerateToken: async () => ({
        allowedContentTypes: ['application/pdf', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/octet-stream'],
      }),
    });

    return response.status(200).json({ clientToken });
  } catch (error) {
    return response.status(400).json({ message: error.message });
  }
}
