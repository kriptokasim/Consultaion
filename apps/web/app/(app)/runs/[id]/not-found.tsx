import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function NotFound() {
    return (
        <div className="flex h-[50vh] flex-col items-center justify-center gap-4 text-center">
            <h2 className="text-2xl font-bold">Debate Not Found</h2>
            <p className="text-muted-foreground">
                The debate you are looking for does not exist or you do not have permission to view it.
            </p>
            <Button asChild>
                <Link href="/runs">Back to Runs</Link>
            </Button>
        </div>
    );
}
