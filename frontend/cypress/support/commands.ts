/// <reference types="cypress" />

// ***********************************************
// This example commands.ts shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************

/**
 * Authentication Commands
 */
Cypress.Commands.add('login', (email: string = 'test@example.com', password: string = 'testpassword123') => {
  cy.session([email, password], () => {
    cy.visit('/login');
    cy.get('input[type="email"]').type(email);
    cy.get('input[type="password"]').type(password);
    cy.get('button[type="submit"]').click();
    
    // Wait for successful login
    cy.url().should('not.include', '/login');
    cy.window().its('localStorage').invoke('getItem', 'access_token').should('exist');
  });
});

Cypress.Commands.add('logout', () => {
  cy.window().then((win) => {
    win.localStorage.removeItem('access_token');
    win.localStorage.removeItem('user');
  });
  cy.visit('/login');
});

/**
 * API Commands
 */
Cypress.Commands.add('apiLogin', (email: string = 'test@example.com', password: string = 'testpassword123') => {
  cy.request({
    method: 'POST',
    url: `${Cypress.env('apiUrl')}/auth/login`,
    body: { email, password }
  }).then((response) => {
    expect(response.status).to.eq(200);
    expect(response.body.success).to.be.true;
    
    const token = response.body.data.access_token;
    const user = response.body.data.user;
    
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('user', JSON.stringify(user));
    
    return { token, user };
  });
});

Cypress.Commands.add('apiRequest', (method: string, endpoint: string, body?: any) => {
  cy.window().then((win) => {
    const token = win.localStorage.getItem('access_token');
    
    cy.request({
      method,
      url: `${Cypress.env('apiUrl')}${endpoint}`,
      body,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      failOnStatusCode: false
    });
  });
});

/**
 * File Upload Commands
 */
Cypress.Commands.add('uploadFile', (selector: string, filePath: string, mimeType: string = 'application/pdf') => {
  cy.get(selector).selectFile({
    contents: Cypress.Buffer.from('test file content'),
    fileName: filePath,
    mimeType: mimeType
  });
});

Cypress.Commands.add('dragAndDropFile', (selector: string, fileName: string, mimeType: string = 'application/pdf') => {
  cy.get(selector).selectFile({
    contents: Cypress.Buffer.from('test file content'),
    fileName: fileName,
    mimeType: mimeType
  }, { action: 'drag-drop' });
});

/**
 * Wait Commands
 */
Cypress.Commands.add('waitForApiResponse', (alias: string, timeout: number = 10000) => {
  cy.wait(alias, { timeout });
});

Cypress.Commands.add('waitForElement', (selector: string, timeout: number = 10000) => {
  cy.get(selector, { timeout }).should('be.visible');
});

Cypress.Commands.add('waitForText', (text: string, timeout: number = 10000) => {
  cy.contains(text, { timeout }).should('be.visible');
});

/**
 * Form Commands
 */
Cypress.Commands.add('fillForm', (formData: Record<string, string>) => {
  Object.entries(formData).forEach(([field, value]) => {
    cy.get(`[data-cy="${field}"], [name="${field}"], #${field}`).clear().type(value);
  });
});

Cypress.Commands.add('submitForm', (selector: string = 'form') => {
  cy.get(selector).submit();
});

/**
 * Navigation Commands
 */
Cypress.Commands.add('navigateTo', (path: string) => {
  cy.visit(path);
  cy.url().should('include', path);
});

Cypress.Commands.add('goBack', () => {
  cy.go('back');
});

/**
 * Assertion Commands
 */
Cypress.Commands.add('shouldBeVisible', (selector: string) => {
  cy.get(selector).should('be.visible');
});

Cypress.Commands.add('shouldNotExist', (selector: string) => {
  cy.get(selector).should('not.exist');
});

Cypress.Commands.add('shouldContainText', (selector: string, text: string) => {
  cy.get(selector).should('contain.text', text);
});

Cypress.Commands.add('shouldHaveClass', (selector: string, className: string) => {
  cy.get(selector).should('have.class', className);
});

/**
 * Mock Commands
 */
Cypress.Commands.add('mockApiResponse', (method: string, endpoint: string, response: any, statusCode: number = 200) => {
  cy.intercept(method, `${Cypress.env('apiUrl')}${endpoint}`, {
    statusCode,
    body: response
  });
});

Cypress.Commands.add('mockApiError', (method: string, endpoint: string, statusCode: number = 500, message: string = 'Server Error') => {
  cy.intercept(method, `${Cypress.env('apiUrl')}${endpoint}`, {
    statusCode,
    body: { error: { message } }
  });
});

/**
 * Utility Commands
 */
Cypress.Commands.add('clearLocalStorage', () => {
  cy.window().then((win) => {
    win.localStorage.clear();
  });
});

Cypress.Commands.add('getLocalStorage', (key: string) => {
  cy.window().then((win) => {
    return win.localStorage.getItem(key);
  });
});

Cypress.Commands.add('setLocalStorage', (key: string, value: string) => {
  cy.window().then((win) => {
    win.localStorage.setItem(key, value);
  });
});

Cypress.Commands.add('scrollToElement', (selector: string) => {
  cy.get(selector).scrollIntoView();
});

Cypress.Commands.add('clickOutside', () => {
  cy.get('body').click(0, 0);
});

// Type definitions for custom commands
declare global {
  namespace Cypress {
    interface Chainable {
      // Authentication
      login(email?: string, password?: string): Chainable<void>
      logout(): Chainable<void>
      apiLogin(email?: string, password?: string): Chainable<{ token: string; user: any }>
      
      // API
      apiRequest(method: string, endpoint: string, body?: any): Chainable<Response<any>>
      
      // File Upload
      uploadFile(selector: string, filePath: string, mimeType?: string): Chainable<void>
      dragAndDropFile(selector: string, fileName: string, mimeType?: string): Chainable<void>
      
      // Wait
      waitForApiResponse(alias: string, timeout?: number): Chainable<void>
      waitForElement(selector: string, timeout?: number): Chainable<void>
      waitForText(text: string, timeout?: number): Chainable<void>
      
      // Forms
      fillForm(formData: Record<string, string>): Chainable<void>
      submitForm(selector?: string): Chainable<void>
      
      // Navigation
      navigateTo(path: string): Chainable<void>
      goBack(): Chainable<void>
      
      // Assertions
      shouldBeVisible(selector: string): Chainable<void>
      shouldNotExist(selector: string): Chainable<void>
      shouldContainText(selector: string, text: string): Chainable<void>
      shouldHaveClass(selector: string, className: string): Chainable<void>
      
      // Mocking
      mockApiResponse(method: string, endpoint: string, response: any, statusCode?: number): Chainable<void>
      mockApiError(method: string, endpoint: string, statusCode?: number, message?: string): Chainable<void>
      
      // Utilities
      clearLocalStorage(): Chainable<void>
      getLocalStorage(key: string): Chainable<string | null>
      setLocalStorage(key: string, value: string): Chainable<void>
      scrollToElement(selector: string): Chainable<void>
      clickOutside(): Chainable<void>
    }
  }
}
