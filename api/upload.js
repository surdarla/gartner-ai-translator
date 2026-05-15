import { handleUpload } from '@vercel/blob';

export default async function handler(request, response) {
  // CORS 헤더 설정
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  // OPTIONS 요청 처리 (Preflight)
  if (request.method === 'OPTIONS') {
    return response.status(200).end();
  }

  // POST 요청만 허용
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Vercel Node.js 런타임에서는 request.body가 이미 JSON으로 파싱되어 있습니다.
    const body = request.body;
    
    if (!process.env.BLOB_READ_WRITE_TOKEN) {
      throw new Error('BLOB_READ_WRITE_TOKEN is missing in environment variables');
    }

    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        return {
          allowedContentTypes: [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint',
            'application/vnd.ms-office'
          ],
          tokenPayload: JSON.stringify({}),
        };
      },
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        console.log('Blob upload completed', blob, tokenPayload);
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    console.error('CRITICAL BLOB ERROR:', error.message);
    return response.status(500).json({ 
      error: 'Internal Server Error', 
      message: error.message,
      suggestion: 'Check if BLOB_READ_WRITE_TOKEN is set in Vercel Project Settings'
    });
  }
}
