# Manuscript Processor Frontend

Angular frontend for the manuscript processing system.

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start development server:**
   ```bash
   npm start
   # or
   ng serve
   ```

3. **Build for production:**
   ```bash
   npm run build
   # or
   ng build
   ```

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── auth/                    # Authentication components
│   │   │   └── login/
│   │   ├── dashboard/               # Dashboard component
│   │   ├── manuscripts/             # Manuscript management components
│   │   └── shared/                  # Shared modules
│   │       ├── components/          # Reusable components
│   │       ├── services/            # Services (API, auth, etc.)
│   │       ├── guards/              # Route guards
│   │       ├── models/              # TypeScript interfaces
│   │       └── interceptors/        # HTTP interceptors
│   ├── environments/                # Environment configurations
│   └── styles.css                   # Global styles with TailwindCSS
├── tailwind.config.js               # TailwindCSS configuration
└── package.json                     # Dependencies and scripts
```

## Features

### ✅ Implemented (Phase 1.3)
- **Angular 20** with standalone components
- **TailwindCSS** for styling
- **HTTP interceptors** for JWT token handling
- **Authentication service** with JWT storage
- **Route guards** for protected routes
- **Error handling service** with user-friendly messages
- **Manuscript service** for API communication
- **Basic login component** with form validation
- **Dashboard component** with manuscripts table
- **Responsive design** with modern UI

### 🔄 To be implemented in later phases
- File upload with progress tracking
- Real-time status updates
- Download functionality
- Advanced filtering and sorting
- Drag-and-drop file upload
- Toast notifications

## Configuration

### Environment Variables
- **Development**: `src/environments/environment.ts`
- **Production**: `src/environments/environment.prod.ts`

Update the `apiUrl` to match your backend server:
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000'  // Backend API URL
};
```

## Development Server

Run `ng serve` for a dev server. Navigate to `http://localhost:4200/`. The application will automatically reload if you change any of the source files.

## Build

Run `ng build` to build the project. The build artifacts will be stored in the `dist/` directory.

## Dependencies

### Core
- **Angular 20**: Modern web framework
- **RxJS**: Reactive programming
- **TypeScript**: Type-safe JavaScript

### UI & Styling
- **TailwindCSS**: Utility-first CSS framework
- **PostCSS**: CSS processing
- **Autoprefixer**: CSS vendor prefixes

### Development
- **Angular CLI**: Development tools
- **Jasmine & Karma**: Testing framework

## Architecture

### Services
- **AuthService**: Handles authentication, JWT tokens, and user state
- **ManuscriptService**: Manages manuscript CRUD operations
- **ErrorHandlerService**: Centralized error handling

### Guards
- **AuthGuard**: Protects routes requiring authentication

### Interceptors
- **AuthInterceptor**: Automatically adds JWT tokens to HTTP requests

### Components
- **LoginComponent**: User authentication form
- **DashboardComponent**: Main application dashboard

This frontend is ready for integration with the FastAPI backend and provides a solid foundation for the manuscript processing workflow.