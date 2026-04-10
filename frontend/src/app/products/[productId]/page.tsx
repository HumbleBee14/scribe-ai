import { ProductWorkspace } from "@/components/products/product-workspace";

interface Props {
  params: Promise<{ productId: string }>;
}

export default async function ProductWorkspacePage({ params }: Props) {
  const { productId } = await params;
  return <ProductWorkspace initialProductId={productId} />;
}
