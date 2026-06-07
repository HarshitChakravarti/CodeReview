import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

async function getPendingReviews() {
  try {
    const res = await fetch("http://127.0.0.1:8000/reviews/pending", { 
      cache: "no-store",
    });
    if (!res.ok) {
      console.error("Failed to fetch pending reviews");
      return [];
    }
    return res.json();
  } catch (e) {
    console.error(e);
    return [];
  }
}

export default async function Home() {
  const pendingReviews = await getPendingReviews();

  return (
    <main className="container mx-auto py-10 px-4">
      <h1 className="text-3xl font-bold mb-8">CodeReview Agent Dashboard</h1>
      
      {pendingReviews.length === 0 ? (
        <p className="text-muted-foreground">No pending reviews waiting for approval.</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {pendingReviews.map((review: any) => (
            <Card key={review.thread_id}>
              <CardHeader>
                <CardTitle>PR #{review.data.pr_number}</CardTitle>
                <CardDescription>Thread: {review.thread_id.substring(0, 8)}...</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="mb-4 text-sm text-muted-foreground">
                  Findings Count: {review.data.findings_count}
                </p>
                <Link href={`/reviews/${review.thread_id}`}>
                  <Button className="w-full">Review & Approve</Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
