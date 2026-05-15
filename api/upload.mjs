import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

export default async function handler(request, response) {
  // CORS 처리 (브라우저가 발급기를 직접 호출할 수 있도록)
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (request.method === 'OPTIONS') {
    return response.status(200).end();
  }

  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { filename, contentType } = request.body;
    
    if (!filename) {
      throw new Error('filename is required in the request body');
    }

    const accountId = process.env.R2_ACCOUNT_ID;
    const accessKeyId = process.env.R2_ACCESS_KEY_ID;
    const secretAccessKey = process.env.R2_SECRET_ACCESS_KEY;
    const bucketName = process.env.R2_BUCKET_NAME || 'uploads';
    const publicDomain = process.env.R2_PUBLIC_DOMAIN; 

    if (!accountId || !accessKeyId || !secretAccessKey || !publicDomain) {
      throw new Error('R2 credentials (ACCOUNT_ID, ACCESS_KEY, SECRET_KEY, PUBLIC_DOMAIN) are not fully configured in environment variables.');
    }

    const s3 = new S3Client({
      region: 'auto',
      endpoint: `https://${accountId}.r2.cloudflarestorage.com`,
      credentials: {
        accessKeyId,
        secretAccessKey,
      },
    });

    // 파일 이름 정제 및 충돌 방지용 타임스탬프 추가
    const safeFilename = `${Date.now()}_${filename.replace(/[^a-zA-Z0-9.]/g, '')}`;
    
    const command = new PutObjectCommand({
      Bucket: bucketName,
      Key: safeFilename,
      ContentType: contentType || 'application/octet-stream',
    });

    // 1시간(3600초) 동안 유효한 Presigned URL 생성
    const uploadUrl = await getSignedUrl(s3, command, { expiresIn: 3600 });
    
    // 최종 다운로드 퍼블릭 URL (끝에 빗금 처리 안전하게)
    const baseUrl = publicDomain.endsWith('/') ? publicDomain.slice(0, -1) : publicDomain;
    const publicUrl = `${baseUrl}/${safeFilename}`;

    return response.status(200).json({ uploadUrl, publicUrl });
  } catch (error) {
    console.error('R2 Presigned URL Generation Error:', error);
    return response.status(400).json({ error: error.message });
  }
}
