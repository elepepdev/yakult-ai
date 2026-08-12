import { useState, useRef, useCallback } from 'react';
import { toaster } from '@/components/ui/toaster';
import { defaultBaseUrl } from '@/context/websocket-context';

export interface AttachedFile {
  id: string;
  name: string;
  mime_type: string;
  kind: 'text' | 'image' | 'pdf' | 'docx';
  data: string;
  size: number;
}

const MAX_FILES = 5;
const MAX_SIZE_MB = 15;
const IMAGE_MAX_WIDTH = 800;
const IMAGE_QUALITY = 0.7;

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function compressImage(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error('Failed to load image'));
      el.src = url;
    });
    let { width, height } = img;
    if (width > IMAGE_MAX_WIDTH) {
      height = Math.round((IMAGE_MAX_WIDTH / width) * height);
      width = IMAGE_MAX_WIDTH;
    }
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return await readAsDataURL(file);
    ctx.drawImage(img, 0, 0, width, height);
    return canvas.toDataURL('image/jpeg', IMAGE_QUALITY);
  } catch {
    return await readAsDataURL(file);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function useFileAttach() {
  const [files, setFiles] = useState<AttachedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearFiles = useCallback(() => setFiles([]), []);

  const openPicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const uploadTextFile = useCallback(async (file: File): Promise<AttachedFile> => {
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch(`${defaultBaseUrl}/upload`, { method: 'POST', body: form });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      throw new Error(err.error || 'Upload failed');
    }
    const result = await resp.json();
    if (result.error) throw new Error(result.error);
    return {
      id: crypto.randomUUID(),
      name: file.name,
      mime_type: file.type || 'application/octet-stream',
      kind: result.kind === 'image' ? 'image' : result.kind === 'pdf' ? 'pdf' : result.kind === 'docx' ? 'docx' : 'text',
      data: result.text || '',
      size: file.size,
    };
  }, []);

  const onFilesSelected = useCallback(async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setFiles((prev) => {
      if (prev.length + fileList.length > MAX_FILES) {
        toaster.create({
          title: `Max ${MAX_FILES} files per message`,
          type: 'error',
          duration: 2000,
        });
        return prev;
      }
      return prev;
    });
    setUploading(true);
    try {
      const picked = Array.from(fileList);
      const remaining = MAX_FILES - files.length;
      const toAdd = picked.slice(0, Math.max(0, remaining));
      if (picked.length > remaining) {
        toaster.create({
          title: `Max ${MAX_FILES} files per message`,
          type: 'error',
          duration: 2000,
        });
      }
      const added: AttachedFile[] = [];
      for (const file of toAdd) {
        if (file.size > MAX_SIZE_MB * 1024 * 1024) {
          toaster.create({
            title: `${file.name} too large (max ${MAX_SIZE_MB} MB)`,
            type: 'error',
            duration: 2500,
          });
          continue;
        }
        if (file.type.startsWith('image/')) {
          const dataUrl = await compressImage(file);
          added.push({
            id: crypto.randomUUID(),
            name: file.name,
            mime_type: file.type,
            kind: 'image',
            data: dataUrl,
            size: file.size,
          });
        } else {
          try {
            added.push(await uploadTextFile(file));
          } catch (err: any) {
            toaster.create({
              title: `Failed to read ${file.name}: ${err.message}`,
              type: 'error',
              duration: 2500,
            });
          }
        }
      }
      setFiles((prev) => [...prev, ...added]);
    } finally {
      setUploading(false);
    }
  }, [files.length, uploadTextFile]);

  return {
    files,
    uploading,
    removeFile,
    clearFiles,
    openPicker,
    onFilesSelected,
    fileInputRef: inputRef,
  };
}
