"use client";

import { useCallback, useRef, useState } from "react";
import { ImagePlus, Send, Square } from "lucide-react";

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
  const fileRef = useRef<HTMLInputElement>(null);

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
    <div className="border-t border-gray-200 bg-white p-4">
      {/* Pending image previews */}
      {pendingImages.length > 0 && (
        <div className="mb-3 flex gap-2 overflow-x-auto">
          {pendingImages.map((img, i) => (
            <div key={i} className="relative">
              <img
                src={img.preview}
                alt="Upload preview"
                className="h-16 w-16 rounded-lg object-cover border border-gray-200"
              />
              <button
                onClick={() =>
                  setPendingImages((prev) => prev.filter((_, j) => j !== i))
                }
                className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        <button
          onClick={() => fileRef.current?.click()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
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
          className="flex-1 resize-none rounded-lg border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
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
