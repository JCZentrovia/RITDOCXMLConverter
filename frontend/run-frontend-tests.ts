#!/usr/bin/env ts-node

import { execSync, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

interface TestConfig {
  type: 'unit' | 'e2e' | 'all';
  coverage: boolean;
  watch: boolean;
  headless: boolean;
  browser: 'chrome' | 'firefox' | 'edge';
  spec?: string;
  environment: 'development' | 'production';
}

class FrontendTestRunner {
  private config: TestConfig;
  private projectRoot: string;

  constructor() {
    this.projectRoot = process.cwd();
    this.config = this.parseArguments();
  }

  private parseArguments(): TestConfig {
    const args = process.argv.slice(2);
    const config: TestConfig = {
      type: 'all',
      coverage: true,
      watch: false,
      headless: true,
      browser: 'chrome',
      environment: 'development'
    };

    for (let i = 0; i < args.length; i++) {
      const arg = args[i];
      const nextArg = args[i + 1];

      switch (arg) {
        case '--type':
          if (['unit', 'e2e', 'all'].includes(nextArg)) {
            config.type = nextArg as 'unit' | 'e2e' | 'all';
            i++;
          }
          break;
        case '--no-coverage':
          config.coverage = false;
          break;
        case '--watch':
          config.watch = true;
          break;
        case '--headed':
          config.headless = false;
          break;
        case '--browser':
          if (['chrome', 'firefox', 'edge'].includes(nextArg)) {
            config.browser = nextArg as 'chrome' | 'firefox' | 'edge';
            i++;
          }
          break;
        case '--spec':
          config.spec = nextArg;
          i++;
          break;
        case '--env':
          if (['development', 'production'].includes(nextArg)) {
            config.environment = nextArg as 'development' | 'production';
            i++;
          }
          break;
        case '--help':
          this.showHelp();
          process.exit(0);
      }
    }

    return config;
  }

  private showHelp(): void {
    console.log(`
Frontend Test Runner

Usage: npm run test:frontend [options]

Options:
  --type <type>        Test type: unit, e2e, all (default: all)
  --no-coverage        Disable coverage reporting
  --watch              Run tests in watch mode
  --headed             Run E2E tests in headed mode (with browser UI)
  --browser <browser>  Browser for E2E tests: chrome, firefox, edge (default: chrome)
  --spec <pattern>     Run specific test files matching pattern
  --env <env>          Environment: development, production (default: development)
  --help               Show this help message

Examples:
  npm run test:frontend                    # Run all tests
  npm run test:frontend -- --type unit    # Run only unit tests
  npm run test:frontend -- --type e2e     # Run only E2E tests
  npm run test:frontend -- --watch        # Run tests in watch mode
  npm run test:frontend -- --spec login   # Run tests matching 'login'
  npm run test:frontend -- --headed       # Run E2E tests with browser UI
    `);
  }

  private setupEnvironment(): void {
    console.log('🔧 Setting up test environment...');
    
    // Set environment variables
    process.env.NODE_ENV = 'test';
    process.env.NG_CLI_ANALYTICS = 'false';
    
    if (this.config.environment === 'production') {
      process.env.API_BASE_URL = 'https://api.manuscript-processor.com';
    } else {
      process.env.API_BASE_URL = 'http://localhost:8000';
    }

    // Ensure test directories exist
    const testDirs = [
      'cypress/e2e',
      'cypress/support',
      'cypress/fixtures',
      'coverage'
    ];

    testDirs.forEach(dir => {
      const fullPath = path.join(this.projectRoot, dir);
      if (!fs.existsSync(fullPath)) {
        fs.mkdirSync(fullPath, { recursive: true });
      }
    });

    console.log('✅ Test environment setup complete');
  }

  private async runUnitTests(): Promise<boolean> {
    console.log('🧪 Running unit tests...');
    
    try {
      const karmaArgs = [
        'test',
        '--no-watch',
        '--browsers=ChromeHeadless'
      ];

      if (this.config.coverage) {
        karmaArgs.push('--code-coverage');
      }

      if (this.config.watch) {
        karmaArgs.splice(1, 1); // Remove --no-watch
        karmaArgs.push('--watch');
      }

      if (this.config.spec) {
        karmaArgs.push(`--include=**/*${this.config.spec}*.spec.ts`);
      }

      const command = `ng ${karmaArgs.join(' ')}`;
      console.log(`Executing: ${command}`);
      
      execSync(command, {
        stdio: 'inherit',
        cwd: this.projectRoot
      });

      console.log('✅ Unit tests completed successfully');
      return true;
    } catch (error) {
      console.error('❌ Unit tests failed:', error);
      return false;
    }
  }

  private async runE2ETests(): Promise<boolean> {
    console.log('🌐 Running E2E tests...');
    
    try {
      const cypressArgs = ['run'];
      
      if (!this.config.headless) {
        cypressArgs[0] = 'open';
      }

      cypressArgs.push(`--browser=${this.config.browser}`);
      
      if (this.config.spec) {
        cypressArgs.push(`--spec=**/*${this.config.spec}*.cy.ts`);
      }

      if (this.config.environment === 'production') {
        cypressArgs.push('--env=baseUrl=https://manuscript-processor.com');
      }

      const command = `npx cypress ${cypressArgs.join(' ')}`;
      console.log(`Executing: ${command}`);
      
      execSync(command, {
        stdio: 'inherit',
        cwd: this.projectRoot
      });

      console.log('✅ E2E tests completed successfully');
      return true;
    } catch (error) {
      console.error('❌ E2E tests failed:', error);
      return false;
    }
  }

  private async generateCoverageReport(): Promise<void> {
    if (!this.config.coverage) return;

    console.log('📊 Generating coverage report...');
    
    try {
      // Merge coverage reports if both unit and E2E tests were run
      if (this.config.type === 'all') {
        const mergeCommand = 'npx nyc merge coverage coverage/merged.json';
        execSync(mergeCommand, { cwd: this.projectRoot });
      }

      // Generate HTML report
      const reportCommand = 'npx nyc report --reporter=html --reporter=text-summary';
      execSync(reportCommand, { cwd: this.projectRoot });

      console.log('✅ Coverage report generated');
      console.log('📁 HTML report available at: coverage/index.html');
    } catch (error) {
      console.warn('⚠️  Coverage report generation failed:', error);
    }
  }

  private async checkTestResults(): Promise<void> {
    const coveragePath = path.join(this.projectRoot, 'coverage');
    const e2eResultsPath = path.join(this.projectRoot, 'cypress/results');
    
    console.log('\n📋 Test Results Summary:');
    console.log('========================');

    // Check unit test coverage
    if (this.config.coverage && fs.existsSync(coveragePath)) {
      try {
        const coverageFile = path.join(coveragePath, 'coverage-summary.json');
        if (fs.existsSync(coverageFile)) {
          const coverage = JSON.parse(fs.readFileSync(coverageFile, 'utf8'));
          const total = coverage.total;
          
          console.log(`📊 Coverage Summary:`);
          console.log(`   Lines: ${total.lines.pct}%`);
          console.log(`   Functions: ${total.functions.pct}%`);
          console.log(`   Branches: ${total.branches.pct}%`);
          console.log(`   Statements: ${total.statements.pct}%`);
        }
      } catch (error) {
        console.warn('⚠️  Could not read coverage summary');
      }
    }

    // Check E2E test results
    if (fs.existsSync(e2eResultsPath)) {
      try {
        const resultFiles = fs.readdirSync(e2eResultsPath);
        console.log(`🌐 E2E Tests: ${resultFiles.length} result files generated`);
      } catch (error) {
        console.warn('⚠️  Could not read E2E results');
      }
    }

    console.log('========================\n');
  }

  private async startDevServer(): Promise<void> {
    if (this.config.type === 'e2e' || this.config.type === 'all') {
      console.log('🚀 Starting development server for E2E tests...');
      
      // Check if server is already running
      try {
        const response = await fetch('http://localhost:4200');
        if (response.ok) {
          console.log('✅ Development server already running');
          return;
        }
      } catch {
        // Server not running, start it
      }

      const serverProcess = spawn('ng', ['serve', '--port=4200'], {
        stdio: 'pipe',
        cwd: this.projectRoot
      });

      // Wait for server to be ready
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          serverProcess.kill();
          reject(new Error('Development server failed to start within 60 seconds'));
        }, 60000);

        serverProcess.stdout?.on('data', (data) => {
          const output = data.toString();
          if (output.includes('Local:') || output.includes('localhost:4200')) {
            clearTimeout(timeout);
            console.log('✅ Development server ready');
            resolve();
          }
        });

        serverProcess.stderr?.on('data', (data) => {
          console.error('Server error:', data.toString());
        });

        serverProcess.on('error', (error) => {
          clearTimeout(timeout);
          reject(error);
        });
      });
    }
  }

  public async run(): Promise<void> {
    console.log('🎯 Frontend Test Runner Starting...');
    console.log(`Configuration: ${JSON.stringify(this.config, null, 2)}\n`);

    try {
      // Setup
      this.setupEnvironment();
      
      if (this.config.type === 'e2e' || this.config.type === 'all') {
        await this.startDevServer();
      }

      let success = true;

      // Run tests based on type
      switch (this.config.type) {
        case 'unit':
          success = await this.runUnitTests();
          break;
        case 'e2e':
          success = await this.runE2ETests();
          break;
        case 'all':
          const unitSuccess = await this.runUnitTests();
          const e2eSuccess = await this.runE2ETests();
          success = unitSuccess && e2eSuccess;
          break;
      }

      // Generate reports
      await this.generateCoverageReport();
      await this.checkTestResults();

      if (success) {
        console.log('🎉 All tests completed successfully!');
        process.exit(0);
      } else {
        console.log('❌ Some tests failed');
        process.exit(1);
      }
    } catch (error) {
      console.error('💥 Test runner failed:', error);
      process.exit(1);
    }
  }
}

// Run the test runner
if (require.main === module) {
  const runner = new FrontendTestRunner();
  runner.run().catch(console.error);
}

export default FrontendTestRunner;
