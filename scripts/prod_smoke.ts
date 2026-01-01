/**
 * Production Smoke Check
 * Quick verification of critical endpoints after deploy
 * 
 * Usage: npx ts-node scripts/prod_smoke.ts
 * 
 * Environment variables:
 * - SMOKE_BASE_URL: Production URL (default: https://consultaion.vercel.app)
 * - SMOKE_API_URL: Production API URL (default: https://consultaion-api.onrender.com)
 */

interface SmokeResult {
    name: string;
    url: string;
    status: number;
    ok: boolean;
    responseTime: number;
    error?: string;
}

const FRONTEND_BASE = process.env.SMOKE_BASE_URL || 'https://consultaion.vercel.app';
const API_BASE = process.env.SMOKE_API_URL || 'https://consultaion.onrender.com';

const FRONTEND_CHECKS = [
    { name: 'Landing Page', path: '/' },
    { name: 'Login Page', path: '/login' },
    { name: 'Register Page', path: '/register' },
    { name: 'Demo Page', path: '/demo' },
    { name: 'Pricing Page', path: '/pricing' },
    { name: 'Models Page', path: '/models' },
    { name: 'Terms Page', path: '/terms' },
    { name: 'Privacy Page', path: '/privacy' },
];

const API_CHECKS = [
    { name: 'API Readiness', path: '/readyz' },
    { name: 'API Health', path: '/healthz' },
    { name: 'Backend Root', path: '/' },
];

async function checkEndpoint(baseUrl: string, path: string, name: string): Promise<SmokeResult> {
    const url = `${baseUrl}${path}`;
    const start = Date.now();

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: { 'User-Agent': 'ConsultaionSmokeTest/1.0' },
            redirect: 'follow',
        });

        const responseTime = Date.now() - start;

        return {
            name,
            url,
            status: response.status,
            ok: response.ok,
            responseTime,
        };
    } catch (error) {
        const responseTime = Date.now() - start;
        return {
            name,
            url,
            status: 0,
            ok: false,
            responseTime,
            error: error instanceof Error ? error.message : 'Unknown error',
        };
    }
}

async function runSmokeTests(): Promise<{ passed: number; failed: number; results: SmokeResult[] }> {
    console.log('\n🔥 Running Production Smoke Tests\n');
    console.log(`Frontend: ${FRONTEND_BASE}`);
    console.log(`API: ${API_BASE}\n`);

    const results: SmokeResult[] = [];
    let passed = 0;
    let failed = 0;

    // Frontend checks
    console.log('📱 Frontend Checks:');
    for (const check of FRONTEND_CHECKS) {
        const result = await checkEndpoint(FRONTEND_BASE, check.path, check.name);
        results.push(result);

        if (result.ok) {
            console.log(`  ✅ ${result.name} (${result.status}) - ${result.responseTime}ms`);
            passed++;
        } else {
            console.log(`  ❌ ${result.name} (${result.status}) - ${result.error || 'Failed'}`);
            failed++;
        }
    }

    // API checks
    console.log('\n🔌 API Checks:');
    for (const check of API_CHECKS) {
        const result = await checkEndpoint(API_BASE, check.path, check.name);
        results.push(result);

        if (result.ok) {
            console.log(`  ✅ ${result.name} (${result.status}) - ${result.responseTime}ms`);
            passed++;
        } else {
            console.log(`  ❌ ${result.name} (${result.status}) - ${result.error || 'Failed'}`);
            failed++;
        }
    }

    return { passed, failed, results };
}

async function main() {
    const { passed, failed, results } = await runSmokeTests();

    console.log('\n' + '─'.repeat(50));
    console.log(`\n📊 Results: ${passed} passed, ${failed} failed\n`);

    if (failed > 0) {
        console.log('❌ SMOKE TESTS FAILED\n');
        console.log('Failed checks:');
        results.filter(r => !r.ok).forEach(r => {
            console.log(`  - ${r.name}: ${r.error || `HTTP ${r.status}`}`);
        });
        process.exit(1);
    } else {
        console.log('✅ ALL SMOKE TESTS PASSED\n');
        process.exit(0);
    }
}

main();
