import { handleUpload } from '@vercel/blob/client';

export default async function handler(request, response) {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (request.method === 'OPTIONS') return response.status(200).end();

  try {
    // 환경 변수를 명시적으로 가져옵니다.
    const token = process.env.BLOB_READ_WRITE_TOKEN;
    
    if (!token) {
      throw new Error('SERVER_ERROR: BLOB_READ_WRITE_TOKEN is not defined in Vercel settings.');
    }

    const jsonResponse = await handleUpload({
      body: request.body,
      request,
      // SDK가 환경 변수를 못 찾는 경우를 대비해 토큰을 명시적으로 전달합니다.
      token: token, 
      onBeforeGenerateToken: async (pathname) => {
        return {
          allowedContentTypes: [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint',
            'application/octet-stream'
          ],
          tokenPayload: JSON.stringify({}),
        };
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    console.error('BLOB_HANDLER_ERROR:', error.message);
    // 에러 발생 시 클라이언트가 원인을 알 수 있게 400 에러와 메시지를 보냅니다.
    return response.status(400).json({ 
      error: 'Upload authentication failed', 
      message: error.message 
    });
  }
}
