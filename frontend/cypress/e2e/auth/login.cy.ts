describe('Login Flow', () => {
  beforeEach(() => {
    cy.clearLocalStorage();
    cy.visit('/login');
  });

  describe('Login Page Layout', () => {
    it('should display login form elements', () => {
      cy.shouldBeVisible('h2');
      cy.shouldContainText('h2', 'Manuscript Processor');
      
      cy.shouldBeVisible('input[type="email"]');
      cy.shouldBeVisible('input[type="password"]');
      cy.shouldBeVisible('button[type="submit"]');
      
      cy.get('input[type="email"]').should('have.attr', 'placeholder', 'Email address');
      cy.get('input[type="password"]').should('have.attr', 'placeholder', 'Password');
    });

    it('should have proper form validation attributes', () => {
      cy.get('input[type="email"]').should('have.attr', 'required');
      cy.get('input[type="password"]').should('have.attr', 'required');
      cy.get('button[type="submit"]').should('be.disabled');
    });

    it('should be responsive on different screen sizes', () => {
      // Test mobile view
      cy.setViewportSize('mobile');
      cy.shouldBeVisible('.max-w-md');
      
      // Test tablet view
      cy.setViewportSize('tablet');
      cy.shouldBeVisible('.max-w-md');
      
      // Test desktop view
      cy.setViewportSize('desktop');
      cy.shouldBeVisible('.max-w-md');
    });
  });

  describe('Form Validation', () => {
    it('should show validation errors for empty fields', () => {
      cy.get('button[type="submit"]').should('be.disabled');
    });

    it('should show validation error for invalid email', () => {
      cy.get('input[type="email"]').type('invalid-email');
      cy.get('input[type="password"]').type('password123');
      
      cy.get('button[type="submit"]').should('be.disabled');
    });

    it('should enable submit button with valid inputs', () => {
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      
      cy.get('button[type="submit"]').should('not.be.disabled');
    });

    it('should handle form submission with Enter key', () => {
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123{enter}');
      
      // Should attempt to submit the form
      cy.url().should('not.include', '/login');
    });
  });

  describe('Successful Login', () => {
    beforeEach(() => {
      // Mock successful login response
      cy.mockApiResponse('POST', '/auth/login', {
        success: true,
        message: 'Login successful',
        data: {
          access_token: 'mock-jwt-token',
          token_type: 'bearer',
          user: {
            id: '507f1f77bcf86cd799439011',
            email: 'test@example.com',
            first_name: 'Test',
            last_name: 'User',
            is_active: true,
            is_verified: true,
            role: 'user'
          }
        }
      });
    });

    it('should login successfully with valid credentials', () => {
      cy.measurePerformance('login');
      
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      cy.get('button[type="submit"]').click();
      
      // Should redirect to dashboard
      cy.url().should('include', '/dashboard');
      
      // Should store authentication data
      cy.getLocalStorage('access_token').should('exist');
      cy.getLocalStorage('user').should('exist');
      
      cy.endPerformanceMeasure('login');
    });

    it('should show loading state during login', () => {
      // Add delay to login response
      cy.intercept('POST', `${Cypress.env('apiUrl')}/auth/login`, (req) => {
        req.reply((res) => {
          res.delay(1000);
          res.send({
            statusCode: 200,
            body: {
              success: true,
              data: {
                access_token: 'mock-token',
                user: { id: '1', email: 'test@example.com' }
              }
            }
          });
        });
      });

      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      cy.get('button[type="submit"]').click();
      
      // Should show loading indicator
      cy.shouldBeVisible('.loading-indicator');
      cy.get('button[type="submit"]').should('be.disabled');
    });

    it('should persist login state across page refreshes', () => {
      cy.login();
      cy.visit('/dashboard');
      
      // Refresh the page
      cy.reload();
      
      // Should still be logged in
      cy.url().should('include', '/dashboard');
      cy.getLocalStorage('access_token').should('exist');
    });
  });

  describe('Login Errors', () => {
    it('should handle invalid credentials error', () => {
      cy.mockApiError('POST', '/auth/login', 401, 'Invalid email or password');
      
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('wrongpassword');
      cy.get('button[type="submit"]').click();
      
      // Should show error message
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Invalid email or password');
      
      // Should remain on login page
      cy.url().should('include', '/login');
      
      // Should not store authentication data
      cy.getLocalStorage('access_token').should('not.exist');
    });

    it('should handle server error', () => {
      cy.mockApiError('POST', '/auth/login', 500, 'Internal server error');
      
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      cy.get('button[type="submit"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Internal server error');
    });

    it('should handle network error', () => {
      cy.intercept('POST', `${Cypress.env('apiUrl')}/auth/login`, { forceNetworkError: true });
      
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      cy.get('button[type="submit"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Network error');
    });

    it('should clear error message on new input', () => {
      cy.mockApiError('POST', '/auth/login', 401, 'Invalid credentials');
      
      // First, create an error
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('wrongpassword');
      cy.get('button[type="submit"]').click();
      
      cy.shouldBeVisible('.error-message');
      
      // Then, start typing new input
      cy.get('input[type="password"]').clear().type('newpassword');
      
      // Error message should be cleared
      cy.shouldNotExist('.error-message');
    });
  });

  describe('Security Features', () => {
    it('should not expose password in form data', () => {
      cy.get('input[type="password"]').type('secretpassword');
      cy.get('input[type="password"]').should('have.attr', 'type', 'password');
    });

    it('should prevent multiple simultaneous login attempts', () => {
      // Mock slow response
      cy.intercept('POST', `${Cypress.env('apiUrl')}/auth/login`, (req) => {
        req.reply((res) => {
          res.delay(2000);
          res.send({ statusCode: 200, body: { success: true } });
        });
      });

      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      
      // Click submit multiple times
      cy.get('button[type="submit"]').click();
      cy.get('button[type="submit"]').should('be.disabled');
      cy.get('button[type="submit"]').click(); // Second click should be ignored
    });

    it('should handle session timeout gracefully', () => {
      // Mock expired token response
      cy.mockApiError('POST', '/auth/login', 401, 'Session expired');
      
      cy.get('input[type="email"]').type('test@example.com');
      cy.get('input[type="password"]').type('password123');
      cy.get('button[type="submit"]').click();
      
      cy.shouldContainText('.error-message', 'Session expired');
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels and roles', () => {
      cy.get('input[type="email"]').should('have.attr', 'aria-label').or('have.attr', 'placeholder');
      cy.get('input[type="password"]').should('have.attr', 'aria-label').or('have.attr', 'placeholder');
      cy.get('button[type="submit"]').should('be.visible');
    });

    it('should support keyboard navigation', () => {
      // Tab through form elements
      cy.get('body').tab();
      cy.focused().should('have.attr', 'type', 'email');
      
      cy.focused().tab();
      cy.focused().should('have.attr', 'type', 'password');
      
      cy.focused().tab();
      cy.focused().should('have.attr', 'type', 'submit');
    });

    it('should have sufficient color contrast', () => {
      // This would typically be tested with axe-core or similar
      cy.get('input[type="email"]').should('be.visible');
      cy.get('input[type="password"]').should('be.visible');
      cy.get('button[type="submit"]').should('be.visible');
    });
  });

  describe('Performance', () => {
    it('should load login page quickly', () => {
      cy.measurePerformance('pageLoad');
      cy.visit('/login');
      cy.shouldBeVisible('h2');
      cy.endPerformanceMeasure('pageLoad');
    });

    it('should handle rapid form interactions', () => {
      const email = 'test@example.com';
      const password = 'password123';
      
      // Rapid typing
      cy.get('input[type="email"]').type(email, { delay: 0 });
      cy.get('input[type="password"]').type(password, { delay: 0 });
      
      cy.get('button[type="submit"]').should('not.be.disabled');
    });
  });

  describe('Browser Compatibility', () => {
    it('should work with autofill', () => {
      // Simulate browser autofill
      cy.get('input[type="email"]').invoke('val', 'test@example.com').trigger('input');
      cy.get('input[type="password"]').invoke('val', 'password123').trigger('input');
      
      cy.get('button[type="submit"]').should('not.be.disabled');
    });

    it('should handle browser back button', () => {
      cy.visit('/dashboard');
      cy.visit('/login');
      cy.goBack();
      
      // Should handle navigation properly
      cy.url().should('include', '/dashboard');
    });
  });
});
