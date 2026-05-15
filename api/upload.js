import { handleUpload } from '@vercel/blob';

export default async function handler(request, response) {
  const body = await request.json();

  try {
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname /*, clientPayload */) => {
        // 여기서 유저 인증 로직을 추가할 수 있습니다.
        return {
          allowedContentTypes: [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint'
          ],
          tokenPayload: JSON.stringify({
            // 유저 ID 등을 담을 수 있음
          }),
        };
      },
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        // 업로드 완료 후 처리 (필요 시)
        console.log('Blob upload completed', blob, tokenPayload);
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    console.error('Blob handleUpload error:', error);
    return response.status(400).json({ error: error.message });
  }
}
