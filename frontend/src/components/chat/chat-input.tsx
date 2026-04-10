"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlus, Send, Square, X } from "lucide-react";

interface Props {
  onSend: (
    text: string,
    images?: Array<{ mediaType: string; data: string }>
  ) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
}

export function ChatInput({ onSend, onStop, disabled, isStreaming }: Props) {
  const [text, setText] = useState("");
  const [pendingImages, setPendingImages] = useState<
    Array<{ mediaType: string; data: string; preview: string }>
  >([]);
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Close lightbox on Escape
  useEffect(() => {
    if (!lightboxSrc) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxSrc(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightboxSrc]);

  const addImageFromFile = useCallback((file: File) => {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      setPendingImages((prev) => [
        ...prev,
        { mediaType: file.type, data: base64, preview: result },
      ]);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleSubmit = () => {
    if (!text.trim() && pendingImages.length === 0) return;
    onSend(
      text,
      pendingImages.length > 0
        ? pendingImages.map(({ mediaType, data }) => ({ mediaType, data }))
        : undefined
    );
    setText("");
    setPendingImages([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    for (const file of Array.from(files)) addImageFromFile(file);
    e.target.value = "";
  };

  // Paste from clipboard (Ctrl+V or right-click paste in textarea)
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of Array.from(items)) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault();
          addImageFromFile(file);
        }
      }
    }
  };

  return (
    <div className="p-4">
      {/* Pending image previews */}
      {pendingImages.length > 0 && (
        <div className="mb-3 flex gap-3 overflow-x-auto pb-1 pt-2 px-1">
          {pendingImages.map((img, i) => (
            <div key={i} className="relative shrink-0">
              {/* Thumbnail — click to preview */}
              <button
                type="button"
                onClick={() => setLightboxSrc(img.preview)}
                className="block"
              >
                <img
                  src={img.preview}
                  alt="Upload preview"
                  className="h-16 w-16 rounded-lg object-cover border border-gray-200 dark:border-neutral-700 hover:opacity-90 transition-opacity"
                />
              </button>
              {/* Remove button — fully visible, sits outside the image */}
              <button
                onClick={() =>
                  setPendingImages((prev) => prev.filter((_, j) => j !== i))
                }
                className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white shadow-md hover:bg-red-600 transition-colors"
                title="Remove image"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox modal */}
      {lightboxSrc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setLightboxSrc(null)}
        >
          <div
            className="relative max-h-[90vh] max-w-[90vw]"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={lightboxSrc}
              alt="Preview"
              className="max-h-[85vh] max-w-[85vw] rounded-xl shadow-2xl object-contain"
            />
            <button
              onClick={() => setLightboxSrc(null)}
              className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-white dark:bg-neutral-800 text-gray-700 dark:text-neutral-200 shadow-lg hover:bg-gray-100 dark:hover:bg-neutral-700 transition-colors"
              title="Close (Esc)"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        <button
          onClick={() => fileRef.current?.click()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-800 text-gray-400 dark:text-neutral-500 hover:text-gray-700 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-700 transition-colors"
          title="Upload or paste an image (weld photo, machine setup)"
        >
          <ImagePlus className="h-5 w-5" />
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileUpload}
          className="hidden"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Ask about the Vulcan OmniPro 220... (paste images with Ctrl+V)"
          rows={1}
          className="flex-1 resize-none rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-4 py-2.5 text-sm text-gray-900 dark:text-neutral-100 placeholder-gray-400 dark:placeholder-neutral-500 focus:border-orange-400 dark:focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-100 dark:focus:ring-orange-900"
          disabled={disabled && !isStreaming}
        />

        {/* Stop button shown while streaming */}
        {isStreaming ? (
          <button
            onClick={onStop}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-red-500 text-white hover:bg-red-400 transition-colors"
            title="Stop response"
          >
            <Square className="h-4 w-4 fill-current" />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!text.trim() && pendingImages.length === 0}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-orange-500 text-white hover:bg-orange-400 disabled:opacity-40 transition-colors"
          >
            <Send className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
