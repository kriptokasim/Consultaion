import { ConsultaionClient } from '../src';

async function main() {
    // Initialize the client with your API endpoint
    const client = new ConsultaionClient({
        baseUrl: process.env.CONSULTAION_API_URL || 'http://localhost:8000',
        apiKey: process.env.CONSULTAION_API_KEY,
    });

    try {
        console.log('Creating a debate with smart routing...\n');

        // Create a debate
        const debate = await client.createDebate({
            prompt: 'What are the ethical implications of AI in healthcare?',
            routing_policy: 'router-smart',
        });

        console.log(`✅ Debate created: ${debate.id}`);
        console.log(`📊 Routed model: ${debate.routed_model}`);

        if (debate.routing_meta?.candidates) {
            console.log('\n🎯 Top routing candidates:');
            debate.routing_meta.candidates.slice(0, 3).forEach((c, i) => {
                console.log(`  ${i + 1}. ${c.model} (score: ${c.total_score.toFixed(3)})`);
            });
        }

        console.log(`\n⏳ Status: ${debate.status}`);

        // Stream events
        console.log('\n📡 Streaming events...\n');

        const cleanup = client.streamEvents(
            debate.id,
            (event) => {
                console.log(`[${event.type}]`, JSON.stringify(event.data, null, 2));
            },
            (error) => {
                console.error('❌ Stream error:', error.message);
            }
        );

        // Stop streaming after 30 seconds
        setTimeout(() => {
            console.log('\n🛑 Stopping stream...');
            cleanup();
        }, 30000);

    } catch (error: any) {
        console.error('❌ Error:', error.message);
        process.exit(1);
    }
}

main();
