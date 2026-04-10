"use client";

import Image from "next/image";
import { DialogShell } from "./dialog-shell";

interface ImageLightboxProps {
  src: string;
  alt: string;
  title?: string;
  onClose: () => void;
}

export function ImageLightbox({
  src,
  alt,
  title = "Image preview",
  onClose,
}: ImageLightboxProps) {
  return (
    <DialogShell
      title={title}
      onClose={onClose}
      sizeClassName="max-w-6xl"
      contentClassName="flex items-center justify-center bg-gray-50 dark:bg-neutral-950 p-4 sm:p-6"
    >
      <div className="relative h-[78vh] w-full">
        <Image
          src={src}
          alt={alt}
          fill
          unoptimized
          sizes="100vw"
          className="rounded-xl object-contain shadow-2xl"
        />
      </div>
    </DialogShell>
  );
}
