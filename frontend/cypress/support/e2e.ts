// ***********************************************************
// This example support/e2e.ts is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.js using ES2015 syntax:
import './commands'

// Alternatively you can use CommonJS syntax:
// require('./commands')

// Hide fetch/XHR requests from command log for cleaner output
const app = window.top;
if (!app.document.head.querySelector('[data-hide-command-log-request]')) {
  const style = app.document.createElement('style');
  style.innerHTML = '.command-name-request, .command-name-xhr { display: none }';
  style.setAttribute('data-hide-command-log-request', '');
  app.document.head.appendChild(style);
}

// Global error handling
Cypress.on('uncaught:exception', (err, runnable) => {
  // returning false here prevents Cypress from failing the test
  // on uncaught exceptions from the application under test
  console.log('Uncaught exception:', err);
  return false;
});

// Custom viewport sizes for responsive testing
Cypress.Commands.add('setViewportSize', (size: 'mobile' | 'tablet' | 'desktop') => {
  const sizes = {
    mobile: [375, 667],
    tablet: [768, 1024],
    desktop: [1280, 720]
  };
  
  const [width, height] = sizes[size];
  cy.viewport(width, height);
});

// Performance monitoring
Cypress.Commands.add('measurePerformance', (name: string) => {
  cy.window().then((win) => {
    win.performance.mark(`${name}-start`);
  });
});

Cypress.Commands.add('endPerformanceMeasure', (name: string) => {
  cy.window().then((win) => {
    win.performance.mark(`${name}-end`);
    win.performance.measure(name, `${name}-start`, `${name}-end`);
    
    const measure = win.performance.getEntriesByName(name)[0];
    cy.log(`Performance: ${name} took ${measure.duration.toFixed(2)}ms`);
  });
});

declare global {
  namespace Cypress {
    interface Chainable {
      setViewportSize(size: 'mobile' | 'tablet' | 'desktop'): Chainable<void>
      measurePerformance(name: string): Chainable<void>
      endPerformanceMeasure(name: string): Chainable<void>
    }
  }
}
