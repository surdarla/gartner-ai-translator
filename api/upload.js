import { handleUpload } from '@vercel/blob/client';

export default async function handler(request, response) {
  const body = await request.json();

  try {
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        // 모든 업로드를 허용하거나, 여기서 세션 체크 등을 할 수 있습니다.
        return {
          allowedContentTypes: [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.ms-powerpoint'
          ],
          tokenPayload: JSON.stringify({
            // 여기에 유저 정보 등을 담을 수 있습니다.
          }),
        };
      },
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        // 업로드 완료 후 실행될 로직 (필요 시)
        console.log('blob upload completed', blob, tokenPayload);
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    return response.status(400).json({ error: error.message });
  }
}
