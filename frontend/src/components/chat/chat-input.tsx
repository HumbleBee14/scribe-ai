"use client";

import { useRef, useState } from "react";
import { ImagePlus, Send } from "lucide-react";

interface Props {
  onSend: (
    text: string,
    images?: Array<{ mediaType: string; data: string }>
  ) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const [pendingImages, setPendingImages] = useState<
    Array<{ mediaType: string; data: string; preview: string }>
  >([]);
  const fileRef = useRef<HTMLInputElement>(null);

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

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    for (const file of Array.from(files)) {
      if (!file.type.startsWith("image/")) continue;
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64 = result.split(",")[1];
        setPendingImages((prev) => [
          ...prev,
          {
            mediaType: file.type,
            data: base64,
            preview: result,
          },
        ]);
      };
      reader.readAsDataURL(file);
    }
    e.target.value = "";
  };

  return (
    <div className="border-t border-neutral-800 bg-neutral-950 p-4">
      {/* Pending image previews */}
      {pendingImages.length > 0 && (
        <div className="mb-3 flex gap-2 overflow-x-auto">
          {pendingImages.map((img, i) => (
            <div key={i} className="relative">
              <img
                src={img.preview}
                alt="Upload preview"
                className="h-16 w-16 rounded-lg object-cover border border-neutral-700"
              />
              <button
                onClick={() =>
                  setPendingImages((prev) => prev.filter((_, j) => j !== i))
                }
                className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-[10px] text-white"
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
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-800 text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"
          title="Upload image (weld photo, setup photo)"
        >
          <ImagePlus className="h-5 w-5" />
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleImageUpload}
          className="hidden"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about the Vulcan OmniPro 220..."
          rows={1}
          className="flex-1 resize-none rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-2.5 text-sm text-white placeholder-neutral-500 focus:border-orange-500 focus:outline-none"
          disabled={disabled}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || (!text.trim() && pendingImages.length === 0)}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-orange-600 text-white hover:bg-orange-500 disabled:opacity-40 disabled:hover:bg-orange-600 transition-colors"
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
