export interface DocConvertMeta {
  filename: string;
  content_type: string;
  size: number;
  status: string;
  pages: number;
  document_id?: string | null;
  errors: string[];
}

export interface DocConvertResponse {
  markdown: string;
  structured: Record<string, any>;
  meta: DocConvertMeta;
}

export interface DocExportResponse {
  blob: Blob;
  filename: string;
}

export async function convertDoc(file: File): Promise<DocConvertResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/doc/convert", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let message = "文档转换失败";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // ignore parse failure and keep fallback message
    }
    throw new Error(message);
  }

  return response.json() as Promise<DocConvertResponse>;
}

export async function exportDoc(content: string, documentId?: string): Promise<DocExportResponse> {
  const response = await fetch("/doc/export", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      content,
      document_id: documentId ?? null,
    }),
  });

  if (!response.ok) {
    let message = "文档导出失败";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // ignore parse failure and keep fallback message
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  return {
    blob,
    filename: parseFilename(response.headers.get("content-disposition")),
  };
}

function parseFilename(contentDisposition: string | null): string {
  if (!contentDisposition) {
    return "document.docx";
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      // ignore decode failure and try ascii filename below
    }
  }

  const asciiMatch = contentDisposition.match(/filename="([^"]+)"/i);
  return asciiMatch?.[1] || "document.docx";
}
