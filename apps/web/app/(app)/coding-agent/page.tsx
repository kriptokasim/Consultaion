"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Code2, GitBranch, TerminalSquare } from "lucide-react";

export default function CodingAgentNewPage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    
    setIsSubmitting(true);
    
    // In a real implementation this would hit the API
    // We simulate creating a run and redirecting
    setTimeout(() => {
      const runId = "ca-" + Math.random().toString(36).substring(2, 9);
      router.push(`/coding-agent/${runId}`);
    }, 1500);
  };

  return (
    <div className="container max-w-4xl py-12 mx-auto">
      <div className="mb-8 text-center space-y-3">
        <div className="inline-flex items-center justify-center p-3 bg-primary/10 rounded-full mb-2">
          <Code2 className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">New Coding Agent Task</h1>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
          Multi-lane evaluation with fast, thinking, verifier, and judge models operating entirely on the free tier.
        </p>
      </div>

      <Card className="border-border shadow-md">
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <CardTitle className="text-xl flex items-center gap-2">
              <TerminalSquare className="w-5 h-5 text-muted-foreground" />
              Task Description
            </CardTitle>
            <CardDescription>
              Describe the coding task, refactoring, or bug you want to fix.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Textarea 
                placeholder="E.g., Refactor the authentication logic to use the new session cookie format and ensure backwards compatibility."
                className="min-h-[150px] text-base resize-y font-mono"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                required
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-muted-foreground" />
                Target Files (Optional)
              </label>
              <Input 
                placeholder="E.g., apps/api/auth.py, apps/web/session.ts"
                value={files}
                onChange={(e) => setFiles(e.target.value)}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated list of files. This helps the router determine task complexity.
              </p>
            </div>
          </CardContent>
          <CardFooter className="bg-muted/30 flex justify-between border-t py-4">
            <p className="text-sm text-muted-foreground">
              Task tier will be automatically classified based on complexity.
            </p>
            <Button type="submit" disabled={isSubmitting || !prompt.trim()} size="lg">
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Initializing Agent...
                </>
              ) : (
                "Start Agent Run"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
