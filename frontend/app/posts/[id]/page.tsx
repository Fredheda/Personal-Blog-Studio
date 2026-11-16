import { PostEditor } from "../../../components/PostEditor";

export default async function PostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main>
      <PostEditor key={id} id={id} />
    </main>
  );
}
