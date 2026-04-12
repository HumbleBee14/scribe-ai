import { ProductWorkspace } from "@/components/products/product-workspace";

interface Props {
  params: Promise<{ productId: string; conversationId: string }>;
}

export default async function ChatPage({ params }: Props) {
  const { productId, conversationId } = await params;
  return <ProductWorkspace initialProductId={productId} initialConversationId={conversationId} />;
}
