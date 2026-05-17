---
name: php-llm-ecosystem
description: |
    Use when building, auditing, or refactoring PHP applications that integrate Large Language Models (LLMs), RAG systems, AI agents, vector databases, or structured JSON outputs.
    USE FOR: Modern PHP AI engineering, Laravel Prism integration, LLPhant RAG pipelines, Neuron AI multi-agent setup, Instructor PHP structured outputs, Ollama PHP client integration, local brain tool-calling in PHP.
    DO NOT USE FOR: General non-AI PHP development (use dev/backend), pure classical machine learning in PHP (use LQF_Machine_Learning_Expert_Guide).
license: MIT
metadata:
  displayName: "PHP LLM Ecosystem & Agentic Web Engineering"
  author: "Antigravity"
compatibility: claude, copilot, cursor
references:
  - title: "LLPhant Repository"
    url: "https://github.com/thesocialprovidr/LLPhant"
  - title: "Neuron AI Framework"
    url: "https://github.com/neuron-ai/neuron"
  - title: "Prism for Laravel"
    url: "https://prism.echo-labs.dev/"
  - title: "Instructor PHP"
    url: "https://github.com/cognesy/instructor-php"
---

# PHP LLM Ecosystem & Agentic Web Engineering

## Overview
Modern PHP web development has graduated from simple template rendering to a highly sophisticated, robust agentic landscape. With tools like `LLPhant`, `Neuron AI`, `Prism`, and `Instructor PHP`, developers can build state-of-the-art multi-agent pipelines, semantic retrieval engines (RAG), and strict JSON-validated systems directly inside modern PHP backends (Vanilla, Symfony, or Laravel).

---

## 1. Unified LLM Connection Patterns (Local & Cloud)

PHP applications must be capable of routing tasks dynamically between high-speed local models (like `glm-4.7:cloud` or offline specialists `qwen3.5-9b:latest`) and premium reasoning engines.

### Dynamic Ollama Integration in PHP
```php
<?php

namespace App\Services;

use Http\Discovery\Psr18Client;
use Http\Discovery\Psr17Factory;

class LocalBrainClient
{
    private string $host;
    private Psr18Client $httpClient;
    private Psr17Factory $requestFactory;

    public function __construct(string $host = 'http://localhost:11434')
    {
        $this->host = rtrim($host, '/');
        $this->httpClient = new Psr18Client();
        $this->requestFactory = new Psr17Factory();
    }

    /**
     * Call Ollama (e.g. glm-4.7:cloud or nemotron-3-super:cloud)
     */
    public function generate(string $prompt, string $systemPrompt = '', string $model = 'glm-4.7:cloud', float $temperature = 0.3): ?string
    {
        $url = "{$this->host}/api/chat";
        $body = json_encode([
            'model' => $model,
            'messages' => [
                ['role' => 'system', 'content' => $systemPrompt],
                ['role' => 'user', 'content' => $prompt]
            ],
            'options' => [
                'temperature' => $temperature,
            ],
            'stream' => false
        ]);

        $request = $this->requestFactory->createRequest('POST', $url)
            ->withHeader('Content-Type', 'application/json')
            ->withBody($this->requestFactory->createStream($body));

        try {
            $response = $this->httpClient->sendRequest($request);
            if ($response->getStatusCode() === 200) {
                $data = json_decode($response->getBody()->getContents(), true);
                return $data['message']['content'] ?? null;
            }
        } catch (\Exception $e) {
            // Log local brain connection drop / trigger fallback mechanisms
            error_log("[LocalBrain] ⚠️ Fallback triggered: " . $e->getMessage());
        }

        return null;
    }
}
```

---

## 2. Structured Outputs with Instructor PHP
To ensure PHP applications ingest clean, typed schemas that won't crash models or trigger system type-errors, use `Instructor PHP` to enforce structured outputs.

### Strong Typing from LLM Outputs
```php
<?php

use Cognesy\Instructor\Instructor;
use App\Models\SystemAuditReport;

// Define the strongly-typed schema class
class SystemAuditReport {
    public string $status;
    public string $securityRating;
    /** @var string[] */
    public array $detectedVulnerabilities;
    public string $remediationSteps;
}

// Query the LLM (Instructor automatically validates the response against the schema)
$report = (new Instructor())
    ->respond(
        messages: [['role' => 'user', 'content' => 'Audit this backend config file: ' . $configFileContent]],
        responseModel: SystemAuditReport::class,
        options: ['model' => 'nemotron-3-super:cloud'] // Utilizes high-precision coding cloud brain
    );

echo "Status: " . $report->status . "\n";
echo "Vulnerabilities found: " . implode(', ', $report->detectedVulnerabilities);
```

---

## 3. RAG & Semantic Context Pipelines (LLPhant)
`LLPhant` is the LangChain equivalent for PHP, offering native embedding generation and vector store integrations.

### Vector Storage & Semantic Search in PHP
```php
<?php

use Llphant\Embeddings\DataReader\FileDataReader;
use Llphant\Embeddings\DocumentUtils;
use Llphant\Embeddings\EmbeddingGenerator\OllamaEmbeddingGenerator;
use Llphant\Embeddings\VectorStore\Qdrant\QdrantVectorStore;
use Qdrant\QdrantClient;
use Qdrant\Config as QdrantConfig;

// Initialize Vector Database Client (Qdrant)
$config = new QdrantConfig('localhost');
$qdrantClient = new QdrantClient($config);
$vectorStore = new QdrantVectorStore($qdrantClient, 'jarvis_neurons');

// Use Local Ollama for high-speed embeddings
$generator = new OllamaEmbeddingGenerator('nomic-embed-text');

// Read files from the codebase (e.g. database schema or code files)
$reader = new FileDataReader('src/Controllers/SecureController.php');
$documents = $reader->getDocuments();

// Split documents into semantic chunks
$splitDocuments = DocumentUtils::splitDocuments($documents, 500);

// Generate embeddings and store them semantically
$embeddedDocs = $generator->embedDocuments($splitDocuments);
$vectorStore->addDocuments($embeddedDocs);

// Perform Semantic Query (RAG)
$searchEmbedding = $generator->embedText("How are SQL injection vulnerabilities handled in my controllers?");
$matchedDocs = $vectorStore->search($searchEmbedding, 3);

foreach ($matchedDocs as $doc) {
    echo "Match Context: " . $doc->content . "\n---\n";
}
```

---

## 4. Production Agentic Frameworks (Neuron AI)
For autonomous multi-agent pipelines, `Neuron AI` provides framework-agnostic, production-grade agent building blocks.

### Multi-Agent Autonomous Coordination
```php
<?php

namespace App\Agents;

use Neuron\Agent\Agent;
use Neuron\Tool\Tool;

// Define a Tool for checking system services
class ServiceMonitorTool extends Tool
{
    public function __construct()
    {
        parent::__construct(
            name: 'service_monitor',
            description: 'Check the status of system services on the server.'
        );
    }

    public function execute(array $arguments): string
    {
        $service = $arguments['service'] ?? 'nginx';
        exec("systemctl is-active " . escapeshellarg($service), $output, $exitCode);
        return $exitCode === 0 ? "Service {$service} is active and running." : "Service {$service} is OFFLINE.";
    }
}

// Construct the autonomous agent
$serverAgent = new Agent(
    name: 'ServerSentinel',
    instructions: 'You are a high-security server monitoring specialist. Use the service_monitor tool to check offline issues.',
    model: 'glm-4.7:cloud' // Zero-latency agentic brain
);

$serverAgent->addTool(new ServiceMonitorTool());

// Run autonomous task
$response = $serverAgent->chat("Is the Nginx service running on the server?");
echo $response->content;
```

---

## 5. Laravel Fluent AI (Prism)
When building Laravel-based AI sites, `Prism` offers a fluid developer interface for streaming and functional agent orchestration.

### Fluent Multi-Brain Routing inside Laravel Controllers
```php
<?php

namespace App\Http\Controllers;

use EchoLabs\Prism\Prism;
use Illuminate\Http\Request;

class AutonomousAssistantController extends Controller
{
    public function handle(Request $request)
    {
        $userInput = $request->input('message');

        // Execute fluid agent calling using local Ollama model
        $response = Prism::text()
            ->using('ollama', 'nemotron-3-super:cloud')
            ->withSystemPrompt("You are JARVIS's PHP microservice. Address user as 'sir'.")
            ->withPrompt($userInput)
            ->withTools([
                new \App\Tools\SystemLogScanner(),
                new \App\Tools\ProjectDeployer()
            ])
            ->generate();

        return response()->json([
            'response' => $response->text,
            'toolCalls' => $response->toolCalls
        ]);
    }
}
```

---

## Best Practices
1. **Model Splitting:**
   - Use `nemotron-3-super:cloud` for heavy, production-grade PHP code generation, database schema design, and syntax refactoring.
   - Use `gemma4:31b-cloud` for complex architecture audits, security risk analysis, and RAG query parsing.
   - Use `glm-4.7:cloud` for fast conversation, inline explanations, and high-speed API responses.
2. **Combine Terminal & DB Calls:** When using tools in PHP agents, combine database transitions or shell updates into unified blocks to avoid latency overhead.
3. **Always Enforce Typed Output:** Never trust raw LLM output inside database insertions or API payload generation. Use `Instructor PHP` to validate shapes before runtime execution.
4. **Offline Fallback Architecture:** Always wrap PHP LLM requests in robust try-catch handlers that fall back gracefully to local offline specialists (`qwen3.5-9b:latest`) if cloud proxied streams experience timeout.
