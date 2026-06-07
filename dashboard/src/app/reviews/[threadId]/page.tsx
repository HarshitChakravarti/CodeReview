"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useParams } from "next/navigation";

export default function ReviewDetail() {
  const params = useParams();
  const threadId = params.threadId as string;
  const router = useRouter();
  
  const [reviewData, setReviewData] = useState<any>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // We fetch all pending reviews and find the one matching our threadId
    fetch("http://127.0.0.1:8000/reviews/pending")
      .then((res) => res.json())
      .then((data) => {
        const found = data.find((r: any) => r.thread_id === threadId);
        if (found) {
          setReviewData(found.data);
        } else {
          toast.error("Review not found. It may have already been processed.");
          router.push("/");
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        toast.error("Failed to load review.");
        setLoading(false);
      });
  }, [threadId, router]);

  const handleAction = async (action: "approve" | "reject") => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/reviews/${threadId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment }),
      });

      if (res.ok) {
        toast.success(`Review ${action}d successfully!`);
        router.push("/");
        router.refresh();
      } else {
        toast.error(`Failed to ${action} review.`);
      }
    } catch (err) {
      console.error(err);
      toast.error(`An error occurred while trying to ${action}.`);
    }
  };

  if (loading) return <div className="p-10 text-center">Loading review...</div>;
  if (!reviewData) return null;

  return (
    <main className="container mx-auto py-10 px-4">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">PR #{reviewData.pr_number} Review</h1>
        <Button variant="outline" onClick={() => router.push("/")}>Back to Dashboard</Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Markdown Review */}
        <Card className="lg:col-span-2 shadow-sm">
          <CardHeader>
            <CardTitle>AI Draft Review</CardTitle>
          </CardHeader>
          <CardContent className="prose dark:prose-invert max-w-none">
            <ReactMarkdown>{reviewData.draft_review}</ReactMarkdown>
          </CardContent>
        </Card>

        {/* Right Column: Human Approval Form */}
        <Card className="h-fit shadow-sm">
          <CardHeader>
            <CardTitle>Human Decision</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Optional Comment to Developer</label>
              <Textarea 
                placeholder="Looks good to me, just fix that one typo..." 
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={4}
              />
            </div>
            <div className="flex flex-col gap-3 pt-2">
              <Button 
                onClick={() => handleAction("approve")} 
                className="w-full bg-green-600 hover:bg-green-700"
              >
                Approve & Post to GitHub
              </Button>
              <Button 
                onClick={() => handleAction("reject")} 
                variant="destructive" 
                className="w-full"
              >
                Reject & Discard
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
