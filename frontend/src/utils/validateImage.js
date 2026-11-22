export const MAX_FILE_SIZE_MB = 10;
export const ACCEPTED_FILE_TYPES = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';

const ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Checks a file before it is accepted for upload.
 * Returns a user-facing message, or null when the file is valid.
 */
export async function validateImage(file) {
  if (!ALLOWED_MIME_TYPES.includes(file.type)) {
    return `"${file.name}" is not a supported format. Please choose a JPG, JPEG, PNG or WEBP image.`;
  }
  if (file.size === 0) {
    return `"${file.name}" is empty. Please choose another image.`;
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `"${file.name}" is ${formatFileSize(file.size)}. The maximum size is ${MAX_FILE_SIZE_MB} MB.`;
  }

  // A valid extension does not guarantee a valid image, so try decoding it.
  try {
    const bitmap = await createImageBitmap(file);
    bitmap.close();
  } catch {
    return `"${file.name}" could not be read as an image. The file may be damaged.`;
  }

  return null;
}
