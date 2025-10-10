describe('Manuscript Download Flow', () => {
  beforeEach(() => {
    cy.login();
    
    // Mock manuscripts list with completed conversions
    cy.mockApiResponse('GET', '/manuscripts*', {
      success: true,
      data: {
        manuscripts: [
          {
            id: '507f1f77bcf86cd799439012',
            filename: 'test-document.pdf',
            status: 'completed',
            file_size: 1024000,
            upload_date: '2024-01-01T00:00:00Z',
            conversion_tasks: [
              {
                id: '507f1f77bcf86cd799439013',
                status: 'completed',
                quality: 'standard',
                result_s3_key: 'converted/test-document.docx'
              }
            ]
          },
          {
            id: '507f1f77bcf86cd799439014',
            filename: 'another-document.pdf',
            status: 'uploaded',
            file_size: 2048000,
            upload_date: '2024-01-02T00:00:00Z',
            conversion_tasks: []
          }
        ],
        total: 2,
        page: 1,
        limit: 10,
        total_pages: 1
      }
    });
    
    cy.visit('/manuscripts');
  });

  describe('Download Interface', () => {
    it('should display download options for completed manuscripts', () => {
      cy.shouldBeVisible('.manuscript-item');
      cy.shouldBeVisible('.download-button');
      cy.shouldBeVisible('.download-dropdown');
    });

    it('should show available file formats', () => {
      cy.get('.download-dropdown').first().click();
      
      cy.shouldBeVisible('.download-option[data-format="pdf"]');
      cy.shouldBeVisible('.download-option[data-format="docx"]');
      
      cy.shouldContainText('.download-option[data-format="pdf"]', 'Original PDF');
      cy.shouldContainText('.download-option[data-format="docx"]', 'Converted DOCX');
    });

    it('should disable download for manuscripts without conversions', () => {
      cy.get('.manuscript-item').eq(1).within(() => {
        cy.get('.download-button').should('be.disabled');
        cy.shouldContainText('.status-text', 'No conversion available');
      });
    });

    it('should show file sizes in download options', () => {
      cy.get('.download-dropdown').first().click();
      
      cy.get('.download-option').each(($option) => {
        cy.wrap($option).should('contain.text', 'MB').or('contain.text', 'KB');
      });
    });
  });

  describe('Single File Download', () => {
    beforeEach(() => {
      // Mock download URL responses
      cy.mockApiResponse('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/download/test-document.pdf?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          file_size: 1024000,
          content_type: 'application/pdf'
        }
      });
    });

    it('should download PDF file successfully', () => {
      cy.measurePerformance('pdfDownload');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      // Should show download progress
      cy.shouldBeVisible('.download-progress');
      cy.shouldContainText('.download-status', 'Preparing download');
      
      // Should trigger file download
      cy.window().its('open').should('have.been.called');
      
      cy.endPerformanceMeasure('pdfDownload');
    });

    it('should download DOCX file successfully', () => {
      cy.mockApiResponse('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/download/test-document.docx?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          file_size: 2048000,
          content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
      });
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="docx"]').click();
      
      cy.shouldBeVisible('.download-progress');
      cy.window().its('open').should('have.been.called');
    });

    it('should show download progress with file size', () => {
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.download-progress');
      cy.shouldContainText('.download-info', '1.0 MB');
      cy.shouldBeVisible('.progress-bar');
    });

    it('should handle download completion', () => {
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.waitForText('Download completed');
      cy.shouldBeVisible('.success-message');
      cy.shouldContainText('.success-message', 'test-document.pdf downloaded successfully');
    });
  });

  describe('Bulk Download', () => {
    beforeEach(() => {
      // Mock bulk download response
      cy.mockApiResponse('POST', '/manuscripts/bulk-download', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/bulk/manuscripts.zip?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          file_count: 2,
          total_size: 3072000,
          zip_filename: 'manuscripts_2024-01-01.zip'
        }
      });
    });

    it('should enable bulk download when manuscripts are selected', () => {
      // Select multiple manuscripts
      cy.get('.manuscript-checkbox').first().check();
      cy.get('.manuscript-checkbox').eq(1).check();
      
      cy.shouldBeVisible('.bulk-actions');
      cy.shouldBeVisible('.bulk-download-button');
      cy.get('.bulk-download-button').should('not.be.disabled');
    });

    it('should show bulk download options', () => {
      cy.get('.manuscript-checkbox').first().check();
      cy.get('.manuscript-checkbox').eq(1).check();
      
      cy.get('.bulk-download-button').click();
      
      cy.shouldBeVisible('.bulk-download-dialog');
      cy.shouldBeVisible('.format-selection');
      cy.shouldBeVisible('input[type="checkbox"][value="pdf"]');
      cy.shouldBeVisible('input[type="checkbox"][value="docx"]');
    });

    it('should download selected manuscripts as ZIP', () => {
      cy.measurePerformance('bulkDownload');
      
      cy.get('.manuscript-checkbox').first().check();
      cy.get('.manuscript-checkbox').eq(1).check();
      
      cy.get('.bulk-download-button').click();
      cy.get('input[type="checkbox"][value="pdf"]').check();
      cy.get('.confirm-bulk-download').click();
      
      cy.shouldBeVisible('.bulk-download-progress');
      cy.shouldContainText('.download-status', 'Preparing ZIP file');
      cy.shouldContainText('.file-count', '2 files');
      cy.shouldContainText('.total-size', '3.0 MB');
      
      cy.window().its('open').should('have.been.called');
      
      cy.endPerformanceMeasure('bulkDownload');
    });

    it('should show bulk download progress', () => {
      cy.get('.manuscript-checkbox').first().check();
      cy.get('.bulk-download-button').click();
      cy.get('input[type="checkbox"][value="pdf"]').check();
      cy.get('.confirm-bulk-download').click();
      
      cy.shouldBeVisible('.bulk-download-progress');
      cy.shouldBeVisible('.progress-bar');
      cy.shouldBeVisible('.progress-percentage');
      cy.shouldBeVisible('.estimated-time');
    });

    it('should allow canceling bulk download', () => {
      cy.get('.manuscript-checkbox').first().check();
      cy.get('.bulk-download-button').click();
      cy.get('input[type="checkbox"][value="pdf"]').check();
      cy.get('.confirm-bulk-download').click();
      
      cy.shouldBeVisible('.cancel-download-button');
      cy.get('.cancel-download-button').click();
      
      cy.shouldNotExist('.bulk-download-progress');
      cy.shouldContainText('.status-message', 'Download cancelled');
    });
  });

  describe('Download History', () => {
    beforeEach(() => {
      // Mock download history
      cy.mockApiResponse('GET', '/manuscripts/download-history*', {
        success: true,
        data: {
          downloads: [
            {
              id: '1',
              filename: 'test-document.pdf',
              download_date: '2024-01-01T12:00:00Z',
              file_size: 1024000,
              format: 'pdf',
              status: 'completed'
            },
            {
              id: '2',
              filename: 'manuscripts_2024-01-01.zip',
              download_date: '2024-01-01T11:00:00Z',
              file_size: 3072000,
              format: 'zip',
              status: 'completed'
            }
          ],
          total: 2
        }
      });
    });

    it('should display download history', () => {
      cy.get('.download-history-button').click();
      
      cy.shouldBeVisible('.download-history-dialog');
      cy.shouldBeVisible('.download-history-list');
      cy.get('.download-history-item').should('have.length', 2);
    });

    it('should show download details in history', () => {
      cy.get('.download-history-button').click();
      
      cy.get('.download-history-item').first().within(() => {
        cy.shouldContainText('.filename', 'test-document.pdf');
        cy.shouldContainText('.file-size', '1.0 MB');
        cy.shouldContainText('.download-date', '2024-01-01');
        cy.shouldContainText('.format', 'PDF');
        cy.shouldContainText('.status', 'Completed');
      });
    });

    it('should allow re-downloading from history', () => {
      cy.mockApiResponse('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/download/test-document.pdf?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString()
        }
      });
      
      cy.get('.download-history-button').click();
      cy.get('.download-history-item').first().within(() => {
        cy.get('.re-download-button').click();
      });
      
      cy.window().its('open').should('have.been.called');
    });

    it('should allow clearing download history', () => {
      cy.mockApiResponse('DELETE', '/manuscripts/download-history', {
        success: true,
        message: 'Download history cleared'
      });
      
      cy.get('.download-history-button').click();
      cy.get('.clear-history-button').click();
      cy.get('.confirm-clear-history').click();
      
      cy.shouldContainText('.empty-history', 'No download history');
    });
  });

  describe('Download Errors', () => {
    it('should handle download URL generation error', () => {
      cy.mockApiError('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', 404, 'File not found');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'File not found');
    });

    it('should handle expired download links', () => {
      cy.mockApiError('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', 410, 'Download link expired');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Download link expired');
      cy.shouldBeVisible('.retry-button');
    });

    it('should handle network errors during download', () => {
      cy.intercept('GET', `${Cypress.env('apiUrl')}/manuscripts/*/download*`, {
        forceNetworkError: true
      });
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Network error');
    });

    it('should handle server errors', () => {
      cy.mockApiError('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', 500, 'Internal server error');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Internal server error');
    });

    it('should allow retry after failed download', () => {
      // First attempt fails
      cy.mockApiError('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', 500, 'Server error');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldBeVisible('.retry-button');
      
      // Mock successful retry
      cy.mockApiResponse('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/download/test-document.pdf?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString()
        }
      });
      
      cy.get('.retry-button').click();
      cy.window().its('open').should('have.been.called');
    });
  });

  describe('Download Security', () => {
    it('should use secure download URLs', () => {
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.wait('@downloadRequest').then((interception) => {
        expect(interception.request.url).to.include('https://');
        expect(interception.request.url).to.include('signature=');
      });
    });

    it('should handle unauthorized download attempts', () => {
      cy.mockApiError('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', 403, 'Access denied');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.error-message');
      cy.shouldContainText('.error-message', 'Access denied');
    });

    it('should validate file integrity', () => {
      cy.mockApiResponse('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/download/test-document.pdf?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          checksum: 'abc123def456'
        }
      });
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldContainText('.download-info', 'Verifying file integrity');
    });
  });

  describe('Download Performance', () => {
    it('should handle large file downloads efficiently', () => {
      cy.mockApiResponse('GET', '/manuscripts/507f1f77bcf86cd799439012/download*', {
        success: true,
        data: {
          download_url: 'https://test-bucket.s3.amazonaws.com/download/large-document.pdf?signature=test',
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          file_size: 50 * 1024 * 1024 // 50MB
        }
      });
      
      cy.measurePerformance('largeFileDownload');
      
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.download-progress');
      cy.shouldContainText('.file-size', '50.0 MB');
      
      cy.endPerformanceMeasure('largeFileDownload');
    });

    it('should show download speed and ETA', () => {
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.shouldBeVisible('.download-speed');
      cy.shouldBeVisible('.estimated-time');
    });

    it('should not block UI during download', () => {
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      // Should still be able to interact with other elements
      cy.get('.manuscripts-header').should('be.visible');
      cy.get('.search-input').should('not.be.disabled');
    });
  });

  describe('Accessibility', () => {
    it('should support keyboard navigation', () => {
      cy.get('body').tab();
      cy.focused().should('have.class', 'download-button');
      
      cy.focused().type('{enter}');
      cy.shouldBeVisible('.download-dropdown');
    });

    it('should have proper ARIA labels', () => {
      cy.get('.download-button').should('have.attr', 'aria-label');
      cy.get('.download-dropdown').should('have.attr', 'aria-expanded');
    });

    it('should announce download progress to screen readers', () => {
      cy.get('.download-dropdown').first().click();
      cy.get('.download-option[data-format="pdf"]').click();
      
      cy.get('.download-progress').should('have.attr', 'aria-live', 'polite');
      cy.get('.progress-percentage').should('have.attr', 'aria-label');
    });
  });
});
