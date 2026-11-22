import { PostEditor } from "../../../components/PostEditor";

export default async function PostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main className="m-0 max-w-none p-0">
      <PostEditor key={id} id={id} />
    </main>
  );
}
